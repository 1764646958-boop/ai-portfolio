# -*- coding: utf-8 -*-
"""
《防线》 · W2/llm/engines.py
LLM 引擎调度层 v0.1 —— 统一三引擎调用管线

覆盖引擎（与集成决策/选题报告对齐）：
- memory_analysis  记忆分析引擎：范本+情感补充 → {drift_direction, magnitude, confidence}
- fake_memory      假记忆生成引擎：真实记忆+信任偏移+变体类型 → {variant_text, distortion_note}
- dialogue         对话生成引擎：上下文+人设+行为摘要 → {dialogue_text, warmth, manipulation, helpfulness}

统一管线：build messages → retry_chat(json_mode) → extract_json → validate_schema
         → 校验失败自动重试（最多 max_retries 次）→ 仍失败降级（返回 None + 日志），
           调用方用预设模板/缓存兜底（对应《防线》"LLM 超时→缓存+轻量规则"降级方案）。

用法示例::

    from deepseek_client import DeepSeekClient
    from engines import run_engine

    client = DeepSeekClient()
    result = run_engine(client, "memory_analysis",
                        template_text="...", player_emotion="有点可爱", anchor_id="CF_CAKE_01")
    # result = {"drift_direction": "human", "magnitude": 2, "confidence": 0.7} 或 None（降级）
"""

import json
import logging
import os
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
    FAKE_MEMORY_SYSTEM_TEMPLATE,
    MEMORY_ANALYSIS_OUTPUT_SCHEMA,
    DIALOGUE_OUTPUT_SCHEMA,
    FAKE_MEMORY_OUTPUT_SCHEMA,
    build_memory_analysis_prompt,
    build_dialogue_generation_prompt,
    build_fake_memory_prompt,
)

# ---------------------------------------------------------------------------
# 日志（本地 logs/engines.log；Godot 侧对应 user://logs/ 约定）
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
# 引擎定义
# ---------------------------------------------------------------------------

class Engine:
    """一个 LLM 引擎 = 构建函数 + 输出 schema + 元信息。"""

    def __init__(self, name, build, schema, description=""):
        self.name = name
        self.build = build
        self.schema = schema
        self.description = description

    def build_messages(self, **kwargs):
        return self.build(**kwargs)

    def __repr__(self):
        return f"<Engine {self.name}>"


ENGINES = {
    "memory_analysis": Engine(
        name="memory_analysis",
        build=build_memory_analysis_prompt,
        schema=MEMORY_ANALYSIS_OUTPUT_SCHEMA,
        description="分析记忆锚点交互，输出信任偏移判定（独立给 trust_bias，不进对话 JSON）",
    ),
    "fake_memory": Engine(
        name="fake_memory",
        build=build_fake_memory_prompt,
        schema=FAKE_MEMORY_OUTPUT_SCHEMA,
        description="基于真实记忆生成语义变体（负面扭曲/正面扭曲/微偏真实）",
    ),
    "dialogue": Engine(
        name="dialogue",
        build=build_dialogue_generation_prompt,
        schema=DIALOGUE_OUTPUT_SCHEMA,
        description="生成 AI 陪伴者台词（dialogue_text 映射 lines[].text，三参数映射 lines[].meta）",
    ),
}


# ---------------------------------------------------------------------------
# 工具函数（自 W1 test_prompts.py 移植，保持原逻辑）
# ---------------------------------------------------------------------------

def extract_json(text):
    """从模型输出中稳健地提取 JSON 对象，返回 dict；失败抛 ValueError。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("模型输出为空")
    text = text.strip()

    # 1) 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) 去掉 ```json ... ``` 代码块围栏
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 3) 截取首尾大括号之间的内容
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
    return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# Mock 客户端（Key 空置时的固定响应，保证全链路可自检）
# ---------------------------------------------------------------------------

class MockClient:
    """模拟 DeepSeek 客户端：retry_chat 返回内置固定 JSON（标注 Mock）。

    仅用于 Key 空置时的结构自检与 pipeline 链路验证，不发起真实网络请求。
    """

    _FIXED = {
        "memory_analysis": {
            "drift_direction": "human",
            "magnitude": 2,
            "confidence": 0.7,
        },
        "fake_memory": {
            "variant_text": "（Mock）去年夏天，旧友迟到了半小时——但那天他其实没有带蛋糕，是我记错了。",
            "distortion_note": "（Mock）篡改归因角度：把温馨细节替换为失落细节",
        },
        "dialogue": {
            "dialogue_text": "（Mock）你最近常想起那家咖啡店。蛋糕……其实他带过，对吗？",
            "warmth": 0.90,
            "manipulation": 0.55,
            "helpfulness": 0.95,
        },
    }

    def __init__(self, engine_name=None):
        self.engine_name = engine_name  # None = 由 retry_chat 的 json 内容自动判断

    def retry_chat(self, messages, json_mode=False, max_retries=2, temperature=0.7):
        """返回 content 字符串（模拟响应）。"""
        # 按 system prompt 中的引擎名匹配，或按默认
        joined = "".join(m.get("content", "") for m in messages if isinstance(m, dict))
        for key in ("假记忆生成引擎", "记忆分析引擎", "对话生成引擎"):
            if key in joined:
                return json.dumps(self._FIXED[
                    {"假记忆生成引擎": "fake_memory",
                     "记忆分析引擎": "memory_analysis",
                     "对话生成引擎": "dialogue"}[key]
                ], ensure_ascii=False)
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
        dict: 通过 schema 校验的输出；全部失败返回 None（调用方降级）
    """
    if name not in ENGINES:
        raise KeyError(f"未知引擎：{name}，可用：{list(ENGINES)}")

    engine = ENGINES[name]

    for attempt in range(max_retries + 1):
        try:
            messages = engine.build_messages(**kwargs)
            content = client.retry_chat(messages, json_mode=True,
                                        max_retries=1, temperature=0.7)
            obj = extract_json(content)
            ok, errors = validate_schema(obj, engine.schema, engine.name)
            if ok:
                return obj
            logger.warning("%s 第 %d 次输出未通过 schema：%s", engine.name, attempt + 1, errors)
        except Exception as e:
            logger.warning("%s 第 %d 次调用异常：%s", engine.name, attempt + 1, e)

        if attempt < max_retries:
            time.sleep(0.5 * (2 ** attempt))  # 指数退避

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
