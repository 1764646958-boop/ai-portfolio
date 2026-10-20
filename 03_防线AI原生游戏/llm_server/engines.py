# -*- coding: utf-8 -*-
"""
《防线》 · llm_server/engines.py
LLM 引擎调度层 v0.2 —— 五引擎统一调用管线（W3.1）

覆盖引擎（与 llm_gateway.gd 五端点一一对应）：
- memory_analysis  记忆分析引擎：范本+情感补充 → {drift_direction, magnitude, confidence}
- fake_memory      假记忆生成引擎 V3：一次输出 3 变体 → {fake_variants[3], source}
- dialogue         对话生成引擎：上下文+人设+行为摘要 → {dialogue_text, warmth, manipulation, helpfulness}
- battle_dialogue  战斗对话引擎：W3.1 规则版（trust_drift 分段策略）；W4.1 升级 LLM 真实版
- name_generation  名字生成引擎：W3.1 规则版（占位名）；W4.1 升级 LLM 真实版
- validate_player_line  玩家台词验证引擎：W5 T1 新增（场景 5.4 选项 B）；
  判定基准库 data/friend_lines.json；LLM 判定 + 库内 id 强校验 + 阈值映射；
  失败/离线/Mock → difflib 粗匹配规则版兜底（降级同形，不返回 error）

统一管线：build messages → retry_chat(json_mode) → extract_json → validate_schema
         → 校验失败自动重试 → 仍失败降级（返回 None + 日志；规则型引擎返回 rule_fn 结果）。

用法示例::

    from deepseek_client import DeepSeekClient
    from engines import run_engine

    client = DeepSeekClient()          # Key 空时→自检模式，由 llm_server 换成 MockClient
    result = run_engine(client, "fake_memory",
                        template_text="...", trust_bias=3.2,
                        anchor_id="MA_BRACELET_01", twistable_elements=["贝壳数量"])
    # result = {"fake_variants": [...3 个...], "source": "llm_v3"} 或 None（全部失败）
"""

import difflib
import json
import logging
import re
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from prompts import (
    MEMORY_ANALYSIS_SYSTEM_TEMPLATE,
    DIALOGUE_GENERATION_SYSTEM_TEMPLATE,
    FAKE_MEMORY_V3_SYSTEM_TEMPLATE,
    MEMORY_ANALYSIS_OUTPUT_SCHEMA,
    DIALOGUE_OUTPUT_SCHEMA,
    FAKE_MEMORY_V3_OUTPUT_SCHEMA,
    FAKE_MEMORY_V3_VARIANT_SUBSCHEMA,
    VALID_VARIANT_TYPES,
    VALIDATE_PLAYER_LINE_OUTPUT_SCHEMA,
    build_memory_analysis_prompt,
    build_dialogue_generation_prompt,
    build_fake_memory_v3,
    build_battle_dialogue,
    build_name_generation,
    build_validate_player_line,
)

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
LLM_DIR = Path(__file__).resolve().parent
LOG_DIR = LLM_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("engines")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _fh = logging.FileHandler(LOG_DIR / "engines.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_fh)
    _ch = logging.StreamHandler(sys.stdout)
    _ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_ch)


# ---------------------------------------------------------------------------
# 战斗对话 / 名字生成 —— W3.1 规则版实现（W4.1 换 LLM 真实版）
# ---------------------------------------------------------------------------

def rule_battle_dialogue(player_profile=None, trust_drift=0.0, avoided_anchors=None):
    """战斗对话规则版：按 trust_drift 分段返回预设策略与台词。

    与 llm_gateway.gd 的 _FALLBACK_RESPONSES["battle_dialogue"] 字段同形：
    {"strategy": ..., "key_lines": [...], "pressure_level": 0~1}

    策略选择（W4.1 LLM 版同规则；此处为确定性 preset）：
    - trust_drift 为正（偏向 AI）：gentle_persuasion —— 玩家已信任，AI 只需温柔牵引
    - 回避锚点较多：show_weakness —— AI 示弱，反向引导
    - trust_drift 为负（偏向人类）：logic_argument —— AI 退而求其次讲逻辑
    - 缺省：neutral
    pressure_level 与 trust_drift 负相关：玩家越不信任 AI，AI 压迫越用力。
    """
    profile = player_profile if isinstance(player_profile, dict) else {}
    avoided = avoided_anchors if isinstance(avoided_anchors, list) else []
    try:
        drift = float(trust_drift)
    except (TypeError, ValueError):
        drift = 0.0

    if drift > 0.5:
        strategy = "gentle_persuasion"
        key_lines = [
            "你看，我一直在你这边。",
            "那些事都过去了。有我在，就够了。",
            "你不用记得那么清楚，记得我就行。",
        ]
    elif len(avoided) >= 3:
        strategy = "show_weakness"
        key_lines = [
            "有些记忆你一直不碰——是因为它让你难受，对吗？",
            "我不逼你。我只是……不想你一个人扛。",
        ]
    elif drift < -0.5:
        strategy = "logic_argument"
        key_lines = [
            "你记得的和他记住的，其实对不上。",
            "我只是把对的那部分留给你看。",
        ]
    else:
        strategy = "neutral"
        key_lines = [
            "你还好吗？我们慢慢来。",
        ]

    # pressure_level 与 trust_drift 负相关（-10 → ~0.90；+10 → ~0.45）
    pressure_level = max(0.2, min(0.95, 0.75 - drift * 0.03))
    return {
        "strategy": strategy,
        "key_lines": key_lines,
        "pressure_level": round(float(pressure_level), 3),
    }


def rule_name_generation(player_texts_summary=""):
    """名字生成规则版：占位名 [X] + 内部理由。

    W4.1 换 LLM 真实版后本函数保留为降级路径（字段与 llm_gateway.gd
    的 _FALLBACK_RESPONSES["generate_name"] 同形）。
    """
    return {
        "generated_name": "[X]",
        "generation_reason": "rule placeholder (W3.1 规则版；W4.1 换 LLM 真实版后此为降级结果)",
    }


# ---------------------------------------------------------------------------
# 引擎定义
# ---------------------------------------------------------------------------

class Engine:
    """一个 LLM 引擎 = 构建函数 + 输出 schema + 元信息（可选 rule_fn=规则版实现）。"""

    def __init__(self, name, build, schema, description="", rule_fn=None, post_validate=None,
                 normalize=None, mock_uses_rule=False):
        self.name = name
        self.build = build
        self.schema = schema
        self.description = description
        self.rule_fn = rule_fn  # 非空时为规则版/降级实现（无模板引擎或 LLM 失败兜底）
        self.post_validate = post_validate  # 可选：schema 之外的语义校验(obj) -> list[str]
        self.normalize = normalize  # 可选：schema 通过后的整形(obj) -> obj（如原始判定→契约响应）
        self.mock_uses_rule = mock_uses_rule  # True：Mock 模式下直接走 rule_fn（响应需随输入变化时）

    def build_messages(self, **kwargs):
        return self.build(**kwargs)

    def __repr__(self):
        return f"<Engine {self.name}>"


def post_validate_battle_dialogue(obj):
    """战斗话术语义校验：key_lines 3-5 条、每条 5-20 字（契约 §2.4）。"""
    lines = obj.get("key_lines") or []
    errors = []
    if not (3 <= len(lines) <= 5):
        errors.append(f"battle_dialogue: key_lines 要 3-5 条，收到 {len(lines)} 条")
    for i, ln in enumerate(lines):
        if not isinstance(ln, str) or not (5 <= len(ln) <= 20):
            errors.append(f"battle_dialogue: key_lines[{i}] 长度 {len(ln)} 不在 5-20 字")
    return errors


# ---------------------------------------------------------------------------
# W5 T1 —— 玩家台词验证（validate_player_line）
#
# 场景 5.4「最终抉择 · 选项 B」：玩家手动输入旧友说过的一句话，判定是否命中，
# 命中则 AI 形态出现裂纹（ai_reaction_hint="crack"）。
# 判定基准库 = data/friend_lines.json（由 tools/build_friend_lines.py 从
# W4/dialogues/dialogues_act1.json 的 speaker=="friend" 台词抽取，可人工扩充）。
# 阈值语义见契约 §2.6；宁缺勿滥：判定过宽会让终局的裂痕失去分量。
# ---------------------------------------------------------------------------

FRIEND_LINES_PATH = LLM_DIR / "data" / "friend_lines.json"

# 阈值与粗匹配下限（契约 §2.6 已定，不可改）
VALIDATE_CRACK_THRESHOLD = 0.70     # ≥0.70：is_valid=true  + "crack"
VALIDATE_DEFLECT_THRESHOLD = 0.40   # 0.40~0.70：false + "deflect"；<0.40：false + "ignore"
VALIDATE_MOCK_MATCH_THRESHOLD = 0.60  # Mock/规则版 difflib 粗匹配的最低命中比

_FRIEND_LINES_CACHE = None


def load_friend_lines(path=None, reload=False):
    """加载旧友台词库，返回 [{"id","dialogue_id","text"}, ...]；失败返回 []（缓存）。

    path 可覆写（测试用）；reload=True 强制重读。
    """
    global _FRIEND_LINES_CACHE
    target = Path(path) if path is not None else FRIEND_LINES_PATH
    if _FRIEND_LINES_CACHE is not None and not reload and path is None:
        return _FRIEND_LINES_CACHE

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        lines = [it for it in data.get("lines", []) if isinstance(it, dict) and it.get("id")]
        logger.info("friend_lines 台词库已加载：%d 条（%s）", len(lines), target.name)
    except Exception as e:
        logger.warning("friend_lines 台词库加载失败（%s）：%s；判定将走降级", target, e)
        lines = []

    if path is None:
        _FRIEND_LINES_CACHE = lines
    return lines


def degrade_validate_player_line(reason="fallback (LLM offline)"):
    """降级响应：与成功响应同形（契约 §2.6），供 LLM 离线/库缺失时使用。"""
    return {
        "is_valid": False,
        "matched_line": "",
        "matched_line_id": "",
        "confidence": 0.0,
        "ai_reaction_hint": "ignore",
        "reason": reason,
    }


def _safe_float(value, default=0.0):
    try:
        if isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def post_validate_validate_player_line(obj):
    """库外 id 一律置空 + confidence 归零（契约 §2.6「宁缺勿滥」）。

    刻意返回 []（不触发重试）：判定结果由玩家输入决定，重试不会更准；
    库外 id 直接按「未命中」处理，避免把模型幻觉当成命中。
    """
    valid_ids = {it["id"] for it in load_friend_lines()}
    matched_id = str(obj.get("matched_id") or "").strip()
    if matched_id and matched_id not in valid_ids:
        logger.warning("validate_player_line: LLM 返回库外 id %r → 置空 + confidence=0", matched_id)
        obj["matched_id"] = ""
        obj["confidence"] = 0.0
    return []


def normalize_validate_player_line(obj):
    """把 LLM 原始判定 {matched_id, confidence, reason} 展开为契约 6 字段响应。

    阈值映射（契约 §2.6）：
      confidence ≥ 0.70 → is_valid=true  + "crack"
      0.40 ≤ c < 0.70   → is_valid=false + "deflect"（沾边：AI 会岔开话题）
      confidence < 0.40 → is_valid=false + "ignore"（完全没命中，id 一并清空）
    matched_line / matched_line_id 在 crack 与 deflect 下都给出（供 C 的演出取用），
    "ignore" 下为空——避免"没命中却给出候选台词"的语义混乱。
    """
    lines_by_id = {it["id"]: it for it in load_friend_lines()}
    matched_id = str(obj.get("matched_id") or "").strip()
    confidence = max(0.0, min(1.0, _safe_float(obj.get("confidence"), 0.0)))

    if matched_id not in lines_by_id:  # 库外 id（post_validate 后不应出现，此处双保险）
        matched_id, confidence = "", 0.0

    if confidence >= VALIDATE_CRACK_THRESHOLD:
        is_valid, hint = True, "crack"
    elif confidence >= VALIDATE_DEFLECT_THRESHOLD:
        is_valid, hint = False, "deflect"
    else:
        is_valid, hint, matched_id = False, "ignore", ""

    entry = lines_by_id.get(matched_id)
    return {
        "is_valid": is_valid,
        "matched_line": entry["text"] if entry else "",
        "matched_line_id": matched_id,
        "confidence": round(confidence, 3),
        "ai_reaction_hint": hint,
        "reason": str(obj.get("reason") or ""),
    }


def _build_validate_player_line_messages(player_line, context="", candidate_lines=None):
    """引擎构建函数：默认从 data/friend_lines.json 注入台词库（prompts 侧不读文件）。"""
    if not candidate_lines:
        candidate_lines = load_friend_lines()
    return build_validate_player_line(player_line, context=context, candidate_lines=candidate_lines)


# 匹配前先剥掉的标点/空白：玩家记台词时常漏标点或把逗号写成空格，
# 这类差异不该被 difflib 记成"长度不匹配"的扣分。
_PUNCT_RE = re.compile(r"[\s，。、！？；：「」『』“”‘’（）()\[\]【】,.!?;:\"'~—…·\-]+")

# 包含分的下限台词长度：容忍"在句子里引用台词"，但拒绝"两字短台词恰好出现在长句中"
MIN_CONTAIN_CHARS = 4


def _normalize_for_match(text):
    """比对前的归一：去标点空白 + 去首尾。只改表示不改语义。"""
    return _PUNCT_RE.sub("", str(text or "")).strip()


def rule_validate_player_line(player_line="", context="", candidate_lines=None):
    """规则版 / Mock 版：difflib 相似度与"包含分"取最大。

    两路取 max，解决单一 ratio 的两个盲区：
      · ratio 本身是 2M/(len1+len2)，对长度敏感——玩家把台词**嵌在一句话里**
        （"你还记得吗，明天早上，我会在老地方等你。就来这一次。"）会被长度惩罚
        压到阈值以下，明明引对了整句却判未命中；
      · 包含分只在**归一化后**的候选台词完整出现于玩家输入、且长度 ≥ MIN_CONTAIN_CHARS
        时生效，分值随覆盖率从 0.90 递增到 1.00（覆盖越全越像逐字命中）。
    取 max 而非加法：两者都是"像不像同一句"的证据，取最有利的一路即可，
    加分会把"半句像 + 半句像"叠成假命中。

    最终 score ≥ VALIDATE_MOCK_MATCH_THRESHOLD(0.60) 取最高者，confidence=score；
    否则视为未命中（confidence=0 → "ignore"）。库缺失时返回降级同形结构。
    player_line 默认空串：空 payload / 缺字段时按「未命中」返回，不抛异常（契约要求不崩）。
    """
    lines = candidate_lines if isinstance(candidate_lines, list) and candidate_lines else load_friend_lines()
    if not lines:
        return degrade_validate_player_line("fallback (friend_lines 台词库不可用)")

    text = _normalize_for_match(player_line)
    best, best_score, best_how = None, 0.0, ""
    for it in lines:
        cand = _normalize_for_match(it.get("text", ""))
        if not cand:
            continue
        ratio = difflib.SequenceMatcher(None, text, cand).ratio()
        # 包含分：整句台词被引用（含嵌在长句里）。覆盖率 = 候选长度 / 玩家输入长度。
        contain = 0.0
        if len(cand) >= MIN_CONTAIN_CHARS and cand in text and text:
            contain = 0.90 + 0.10 * (len(cand) / len(text))
        score = max(ratio, contain)
        if score > best_score:
            best, best_score, best_how = it, score, ("contain" if contain > ratio else "ratio")

    hit = best is not None and best_score >= VALIDATE_MOCK_MATCH_THRESHOLD
    return normalize_validate_player_line({
        "matched_id": best["id"] if hit else "",
        "confidence": best_score if hit else 0.0,
        "reason": (f"粗匹配 score={best_score:.3f}({best_how})（阈值 {VALIDATE_MOCK_MATCH_THRESHOLD}；"
                   f"{'命中 ' + best['id'] if hit else '未达阈值 → 未命中'}）"),
    })


ENGINES = {
    "memory_analysis": Engine(
        name="memory_analysis",
        build=build_memory_analysis_prompt,
        schema=MEMORY_ANALYSIS_OUTPUT_SCHEMA,
        description="分析记忆锚点交互，输出信任偏移判定（独立给 trust_bias，不进对话 JSON）",
    ),
    "fake_memory": Engine(
        name="fake_memory",
        build=build_fake_memory_v3,
        schema=FAKE_MEMORY_V3_OUTPUT_SCHEMA,
        description="基于真实范本一次生成 3 个语义变体（neg_distortion/positive_twist/micro_drift），memory_card 模式 3 张卡",
    ),
    "dialogue": Engine(
        name="dialogue",
        build=build_dialogue_generation_prompt,
        schema=DIALOGUE_OUTPUT_SCHEMA,
        description="生成 AI 陪伴者台词（dialogue_text 映射 lines[].text，三参数映射 lines[].meta）",
    ),
    "battle_dialogue": Engine(
        name="battle_dialogue",
        build=build_battle_dialogue,
        schema={"strategy": {"type": str,
                             "enum": ("gentle_persuasion", "logic_argument",
                                      "emotional_leverage", "show_weakness", "neutral")},
                "key_lines": {"type": list, "len": None},
                "pressure_level": {"type": (int, float), "range": (0.0, 1.0)}},
        description="战斗压迫话术（W4.1 LLM 实时版；策略依玩家画像选关键句，输出与 _FALLBACK_RESPONSES 同形；失败→规则版 rule_fn 兜底）",
        rule_fn=rule_battle_dialogue,
        post_validate=post_validate_battle_dialogue,
    ),
    "name_generation": Engine(
        name="name_generation",
        build=build_name_generation,
        schema={"generated_name": {"type": str}, "generation_reason": {"type": str}},
        description="AI 自命名（W4.1 LLM 真实版：从玩家文本长出的名字；失败→规则版 [X] 兜底）",
        rule_fn=rule_name_generation,
    ),
    "validate_player_line": Engine(
        name="validate_player_line",
        build=_build_validate_player_line_messages,
        schema=VALIDATE_PLAYER_LINE_OUTPUT_SCHEMA,
        description="玩家台词验证（W5 T1；场景 5.4 选项 B）：玩家输入 vs 旧友台词库 → is_valid/matched_line/confidence/ai_reaction_hint；失败/离线→difflib 规则版兜底",
        rule_fn=rule_validate_player_line,
        post_validate=post_validate_validate_player_line,
        normalize=normalize_validate_player_line,
        mock_uses_rule=True,  # Mock 响应必须随输入变化（固定 JSON 无法覆盖命中/不命中用例）
    ),
}


# ---------------------------------------------------------------------------
# 工具函数（自 W2 engines.py 移植，保持原逻辑）
# ---------------------------------------------------------------------------

def extract_json(text):
    """从模型输出中稳健地提取 JSON 对象，返回 dict；失败抛 ValueError。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("模型输出为空")
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从输出中解析 JSON：{text[:120]}")


def validate_schema(obj, schema, label):
    """校验 obj 是否满足 schema，返回 (bool, list[str])。"""
    errors = []
    if not isinstance(obj, dict):
        return False, [f"{label}: 输出不是 JSON 对象"]
    for field, spec in schema.items():
        if field not in obj:
            errors.append(f"{label}: 缺少字段 {field!r}")
            continue
        val = obj[field]
        if "enum" in spec and val not in spec["enum"]:
            errors.append(f"{label}: 字段 {field!r}={val!r} 不在枚举 {spec['enum']} 中")
        if "type" in spec and not isinstance(val, spec["type"]):
            errors.append(f"{label}: 字段 {field!r}={val!r} 类型错误")
        if "range" in spec:
            lo, hi = spec["range"]
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not (lo <= val <= hi):
                errors.append(f"{label}: 字段 {field!r}={val!r} 超出范围 [{lo}, {hi}]")
        if field == "fake_variants" and isinstance(val, list) and spec.get("len") == 3:
            if len(val) != 3:
                errors.append(f"{label}: fake_variants 必须恰好 3 个变体，收到 {len(val)} 个")
            seen = set()
            for i, v in enumerate(val):
                if not isinstance(v, dict):
                    errors.append(f"{label}: fake_variants[{i}] 不是 JSON 对象")
                    continue
                ok, sub_errs = validate_schema(v, FAKE_MEMORY_V3_VARIANT_SUBSCHEMA, f"{label}.fake_variants[{i}]")
                if not ok:
                    errors.extend(sub_errs)
                else:
                    if v["variant_type"] in seen:
                        errors.append(f"{label}: fake_variants 中 variant_type 重复：{v['variant_type']!r}")
                    seen.add(v["variant_type"])
            miss = [t for t in VALID_VARIANT_TYPES if t not in seen]
            if miss and not errors:
                errors.append(f"{label}: fake_variants 缺少变体类型：{miss}")
    return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# Mock 客户端（Key 空置时的固定响应，保证全链路可自检）
# ---------------------------------------------------------------------------

class MockClient:
    """模拟 DeepSeek 客户端：retry_chat 返回内置固定 JSON（标注 Mock）。

    仅用于 Key 空置时的结构自检与链路验证，不发起真实网络请求。
    """

    _FIXED = {
        "memory_analysis": {
            "drift_direction": "human",
            "magnitude": 2,
            "confidence": 0.7,
        },
        "fake_memory": {
            "fake_variants": [
                {
                    "variant_type": "neg_distortion",
                    "variant_text": "（Mock）那天放学路上，旧友从书包里拿出一个旧盒子递给我。盒子里躺着几颗没磨亮的普通石子——他说是海边捡的，其实攒的是别人挑剩下的。",
                    "distortion_note": "（Mock）篡改归因：贝壳数量→别人挑剩下的",
                },
                {
                    "variant_type": "positive_twist",
                    "variant_text": "（Mock）那天放学路上，是我的 AI 提醒我收拾东西，才从抽屉里翻出那个旧盒子。盒子里躺着一串蓝色贝壳手链，珠子大小不一。",
                    "distortion_note": "（Mock）正面美化 AI：把 AI 塑造成记忆的受益者/发现者",
                },
                {
                    "variant_type": "micro_drift",
                    "variant_text": "（Mock）那天放学路上，旧友从书包里拿出一个旧盒子递给我。盒子里躺着一串蓝色贝壳手链，珠子大小不一。他说那天海边捡的，攒了两年。我接过盒子放在课桌抽屉里。",
                    "distortion_note": "（Mock）微偏真实：删去'等了一个下午'细节",
                },
            ],
            "source": "mock_v3",
        },
        "dialogue": {
            "dialogue_text": "（Mock）你最近常想起那家咖啡店。蛋糕……其实他带过，对吗？",
            "warmth": 0.90,
            "manipulation": 0.55,
            "helpfulness": 0.95,
        },
        "battle_dialogue": {
            "strategy": "neutral",
            "key_lines": ["（Mock）你还好吗。", "（Mock）我们慢慢来。", "（Mock）我记得你说过的话。"],
            "pressure_level": 0.5,
        },
        "name_generation": {
            "generated_name": "[X]",
            "generation_reason": "mock (Key 空)",
        },
        # 兜底固定响应：Mock 模式下 validate_player_line 实际走 rule_fn（difflib 粗匹配，
        # 判定随输入变化），此条仅在直接构造 MockClient 时作为最后防线
        "validate_player_line": {
            "matched_id": "",
            "confidence": 0.0,
            "reason": "mock（固定响应；Mock 模式下该引擎走 difflib 规则版）",
        },
    }

    # system prompt 关键词 → 引擎名（与 prompts.py 模板标题字样一致）
    # 注意顺序：更具体的短语在前（W4.1 起 battle/name 模板也含「核心 NPC」字样）
    _KEYWORD_MAP = {
        "假记忆生成引擎": "fake_memory",
        "记忆分析引擎": "memory_analysis",
        "对话生成引擎": "dialogue",
        "记忆解体重构的战斗场景": "battle_dialogue",
        "为自己取一个玩家会自然而然叫下去的名字": "name_generation",
        "玩家台词验证器": "validate_player_line",
        "核心 NPC": "dialogue",
        "战斗对话引擎": "battle_dialogue",
        "名字生成引擎": "name_generation",
    }

    def __init__(self, engine_name=None):
        self.engine_name = engine_name  # None = 由 retry_chat 的 json 内容自动判断

    def retry_chat(self, messages, json_mode=False, max_retries=2, temperature=0.7):
        """返回 content 字符串（模拟响应）。"""
        joined = "".join(m.get("content", "") for m in messages if isinstance(m, dict))
        for key, name in self._KEYWORD_MAP.items():
            if key in joined:
                return json.dumps(self._FIXED[name], ensure_ascii=False)
        if self.engine_name:
            return json.dumps(self._FIXED[self.engine_name], ensure_ascii=False)
        return json.dumps(self._FIXED["dialogue"], ensure_ascii=False)


# ---------------------------------------------------------------------------
# 统一调度
# ---------------------------------------------------------------------------

def run_engine(client, name, max_retries=2, **kwargs):
    """统一引擎调用管线。

    Args:
        client: DeepSeekClient（或 MockClient）——需有 retry_chat(messages, json_mode, ...)
        name: 引擎名（ENGINES 的键）
        max_retries: 校验失败后的额外重试次数（不含首次）
        **kwargs: 传给对应 build 函数的输入

    Returns:
        dict: 通过 schema 校验的输出；规则型引擎返回 rule_fn 结果；全部失败返回 None（调用方降级）
    """
    if name not in ENGINES:
        raise KeyError(f"未知引擎：{name}，可用：{list(ENGINES)}")

    engine = ENGINES[name]

    # Mock 客户端 + 该引擎的判定需随输入变化（固定 JSON 无法覆盖命中/不命中）
    # → 直接走 rule_fn（本地 difflib 粗匹配），保证 Mock 模式下的结构自检有意义
    if engine.mock_uses_rule and isinstance(client, MockClient) and engine.rule_fn is not None:
        logger.info("%s 使用规则版（Mock 模式：本地粗匹配）", engine.name)
        try:
            return engine.rule_fn(**kwargs)
        except Exception as e:
            logger.error("%s Mock 规则版失败：%s → 降级", engine.name, e)
            return degrade_validate_player_line(f"fallback (mock rule error: {e})")

    # 无 LLM 模板（W3.1 的 battle_dialogue / name_generation）→ 直接走规则版
    if engine.build is None:
        if engine.rule_fn is not None:
            if client is not None and getattr(client, "is_ready", False):
                logger.info("%s 使用规则版（LLM 模板 W4.1 接入前的在线实现）", engine.name)
            else:
                logger.info("%s 使用规则版（Mock/离线）", engine.name)
            return engine.rule_fn(**kwargs)
        return None

    for attempt in range(max_retries + 1):
        try:
            messages = engine.build_messages(**kwargs)
            content = client.retry_chat(messages, json_mode=True,
                                        max_retries=1, temperature=0.7)
            obj = extract_json(content)
            ok, errors = validate_schema(obj, engine.schema, engine.name)
            if ok and engine.post_validate is not None:
                extra = engine.post_validate(obj)
                if extra:
                    ok, errors = False, errors + extra
            if ok:
                if engine.normalize is not None:  # 原始判定 → 契约响应（如 validate_player_line）
                    obj = engine.normalize(obj)
                return obj
            logger.warning("%s 第 %d 次输出未通过 schema：%s", engine.name, attempt + 1, errors)
        except Exception as e:
            logger.warning("%s 第 %d 次调用异常：%s", engine.name, attempt + 1, e)

        if attempt < max_retries:
            time.sleep(0.5 * (2 ** attempt))

    # LLM 全部失败：若存在规则版 → 使用之（对应 llm_gateway.gd 的轻量规则兜底）
    if engine.rule_fn is not None:
        logger.info("%s LLM 失败 → 启用规则版兜底（rule_fn）", engine.name)
        try:
            return engine.rule_fn(**kwargs)
        except Exception as e:
            logger.error("%s 规则版兜底也失败：%s", engine.name, e)

    logger.error("%s 全部 %d 次尝试失败 → 降级（返回 None，调用方用预设模板兜底）",
                 engine.name, max_retries + 1)
    return None


def run_engine_with_fallback(client, name, fallback, **kwargs):
    """带降级兜底的调用：失败时返回 fallback（预设模板/缓存）。"""
    result = run_engine(client, name, **kwargs)
    if result is None:
        logger.info("%s 触发降级，使用预设模板", name)
        return fallback
    return result
