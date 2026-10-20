# -*- coding: utf-8 -*-
"""
《防线》 · W1/llm/test_prompts.py
Prompt 原型 v0.1 —— 测试脚本

行为：
  - 检测 DEEPSEEK_API_KEY：
      * 为空 → 「Mock 模式」：只做结构自检（校验两个 Prompt 模板内容完整、JSON Schema 字段齐全、
                测试用例就绪），打印 Mock 自检报告，不发起真实网络请求。
      * 非空 → 真实 DeepSeek 调用：同一输入连测 3 次，打印三次输出对比，验证结构合法、输出稳定。

硬约束：所有调用走 DeepSeek；JSON 必须能被 json.loads 解析；Key 为空不能崩溃。
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
W1_DIR = os.path.dirname(LLM_DIR)
sys.path.insert(0, LLM_DIR)

from prompts import (
    MEMORY_ANALYSIS_SYSTEM_TEMPLATE,
    DIALOGUE_GENERATION_SYSTEM_TEMPLATE,
    MEMORY_ANALYSIS_OUTPUT_SCHEMA,
    DIALOGUE_OUTPUT_SCHEMA,
    build_memory_analysis_prompt,
    build_dialogue_generation_prompt,
)

# ---------- 配置读取 ----------
for _p in (os.path.join(W1_DIR, ".env"), os.path.join(LLM_DIR, ".env")):
    load_dotenv(_p)

DEEPSEEK_API_KEY = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
DEEPSEEK_BASE_URL = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip()
DEEPSEEK_MODEL = (os.getenv("DEEPSEEK_MODEL") or "deepseek-chat").strip()

# ---------- 真实测试用例（与设计文档一致，勿改动） ----------
MEMORY_CASE = {
    "template_text": "咖啡店墙上的照片：去年夏天，旧友迟到了半小时但带了栗子蛋糕。你觉得那天的他______",
    "player_emotion": "有点可爱",
    "anchor_id": "anchor_cafe_photo_01",
}

DIALOGUE_CASE = {
    "context": "玩家刚完成一个记忆锚点交互，选择跳过没看旧友的短信",
    "npc_character": "温柔不说谎的AI",
    "player_history_summary": "对旧友疏离、易愧疚",
}

RUN_TIMES = 3
TEMPERATURE = 0.7


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def banner(text):
    print("=" * 72)
    print(f"  {text}")
    print("=" * 72)


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
# Mock 模式：结构自检
# ---------------------------------------------------------------------------

def mock_self_check():
    banner("Mock 模式 · 结构自检报告（未发起真实 API 调用）")
    print("【说明】当前 DEEPSEEK_API_KEY 为空，仅做静态结构自检。")
    print("【待办】待填入真实 Key 后重跑本脚本，即可得到真实 3 次稳定性测试。\n")

    checks = []

    # 1. 记忆分析引擎 · Prompt 模板完整
    checks.append((
        "记忆分析引擎 · Prompt 模板内容完整",
        all(k in MEMORY_ANALYSIS_SYSTEM_TEMPLATE for k in
            ("记忆分析引擎", "情感温度", "归因模式", "选择性回避", "自我暴露深度")),
        "含引擎名 + 四个分析维度",
    ))
    checks.append((
        "记忆分析引擎 · Schema 字段齐全（代码级）",
        set(MEMORY_ANALYSIS_OUTPUT_SCHEMA) == {"drift_direction", "magnitude", "confidence"},
        "字段: drift_direction / magnitude / confidence",
    ))
    checks.append((
        "记忆分析引擎 · Prompt 内声明输出字段",
        all(f'"{f}"' in MEMORY_ANALYSIS_SYSTEM_TEMPLATE for f in MEMORY_ANALYSIS_OUTPUT_SCHEMA),
        "模板中的 JSON 示例字段齐全",
    ))

    # 2. 对话生成引擎 · Prompt 模板完整
    checks.append((
        "对话生成引擎 · Prompt 模板内容完整",
        all(k in DIALOGUE_GENERATION_SYSTEM_TEMPLATE for k in
            ("从不正面说谎", "温柔服务于目标", "不暴露真实意图")),
        "含三条人设硬约束",
    ))
    checks.append((
        "对话生成引擎 · Schema 字段齐全（代码级）",
        set(DIALOGUE_OUTPUT_SCHEMA) == {"dialogue_text", "warmth", "manipulation", "helpfulness"},
        "字段: dialogue_text / warmth / manipulation / helpfulness",
    ))
    checks.append((
        "对话生成引擎 · Prompt 内声明输出字段",
        all(f'"{f}"' in DIALOGUE_GENERATION_SYSTEM_TEMPLATE for f in DIALOGUE_OUTPUT_SCHEMA),
        "模板中的 JSON 示例字段齐全",
    ))

    # 3. 构建函数可正常格式化（无残留占位符）
    mem_msgs = build_memory_analysis_prompt(**MEMORY_CASE)
    dlg_msgs = build_dialogue_generation_prompt(**DIALOGUE_CASE)
    mem_system = mem_msgs[0]["content"]
    dlg_system = dlg_msgs[0]["content"]

    checks.append((
        "记忆分析引擎 · 构建函数格式化正常",
        all(f"{{{k}}}" not in mem_system for k in MEMORY_CASE),
        "输入已注入，无残留占位符",
    ))
    checks.append((
        "对话生成引擎 · 构建函数格式化正常",
        all(f"{{{k}}}" not in dlg_system for k in DIALOGUE_CASE),
        "输入已注入，无残留占位符",
    ))
    checks.append((
        "messages 结构合法",
        (len(mem_msgs) == 2 and len(dlg_msgs) == 2
         and all(m["role"] in ("system", "user") and m["content"].strip() for m in mem_msgs + dlg_msgs)),
        "每引擎均含 system + user，且内容非空",
    ))

    # 4. 测试用例已就绪
    checks.append((
        "记忆分析用例 · 就绪",
        all(str(v).strip() for v in MEMORY_CASE.values()),
        "template_text / player_emotion / anchor_id 均非空",
    ))
    checks.append((
        "对话生成用例 · 就绪",
        all(str(v).strip() for v in DIALOGUE_CASE.values()),
        "context / npc_character / player_history_summary 均非空",
    ))

    # 打印逐项结果
    n_pass = 0
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}  —— {detail}")
        n_pass += ok

    print("\n" + "=" * 72)
    print(f"  自检结论：{n_pass}/{len(checks)} 项通过")
    print("=" * 72)

    # 打印完整 Prompt 供人工审阅
    print("\n" + "─" * 72)
    print("【记忆分析引擎 · System Prompt（已注入用例）】")
    print("─" * 72)
    print(mem_system)
    print("\n" + "─" * 72)
    print("【对话生成引擎 · System Prompt（已注入用例）】")
    print("─" * 72)
    print(dlg_system)


# ---------------------------------------------------------------------------
# 真实模式：连测 3 次
# ---------------------------------------------------------------------------

def call_model(client, messages):
    resp = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content


def run_engine(name, build_fn, case, schema, client):
    messages = build_fn(**case)
    banner(f"引擎：{name} · 同一输入连测 {RUN_TIMES} 次（temperature={TEMPERATURE}）")

    results = []
    for i in range(1, RUN_TIMES + 1):
        print(f"\n--- 第 {i} 次 ---")
        try:
            content = call_model(client, messages)
            print(f"原始输出：{content}")
            obj = extract_json(content)
            ok, errors = validate_schema(obj, schema, name)
            print(f"解析+校验：{'通过' if ok else '失败'}  {json.dumps(obj, ensure_ascii=False)}")
            for e in errors:
                print(f"   - {e}")
            results.append({"ok": ok, "obj": obj, "errors": errors})
        except Exception as e:
            print(f"调用/解析异常：{e}")
            results.append({"ok": False, "obj": None, "errors": [str(e)]})

    # 稳定性小结
    valid = [r for r in results if r["ok"]]
    print(f"\n{'─' * 72}")
    print(f"{name} · 稳定性小结")
    print(f"  结构合法：{len(valid)}/{RUN_TIMES} 次")
    if valid:
        for f, spec in schema.items():
            vals = [r["obj"][f] for r in valid if f in r["obj"]]
            if not vals:
                continue
            if "enum" in spec:
                print(f"  {f}: {vals}")
            elif "range" in spec:
                print(f"  {f}: {vals}  (min={min(vals):.3f}, max={max(vals):.3f})")
    if len(valid) == RUN_TIMES:
        print("  结论：结构合法、输出稳定 ✅")
    else:
        print("  结论：存在不稳定/非法输出，请检查 ❌")
    print("─" * 72)
    return results


def run_real_test():
    try:
        from openai import OpenAI
    except ImportError:
        print("❌ 未安装 openai 库，无法发起真实调用。请 `pip install openai`。")
        return

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    run_engine("记忆分析引擎", build_memory_analysis_prompt, MEMORY_CASE,
               MEMORY_ANALYSIS_OUTPUT_SCHEMA, client)
    run_engine("对话生成引擎", build_dialogue_generation_prompt, DIALOGUE_CASE,
               DIALOGUE_OUTPUT_SCHEMA, client)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    banner("《防线》· Prompt 原型 v0.1 · 测试")
    print(f"  DEEPSEEK_API_KEY : {'已配置' if DEEPSEEK_API_KEY else '空置（进入 Mock 模式）'}")
    print(f"  base_url         : {DEEPSEEK_BASE_URL}")
    print(f"  model            : {DEEPSEEK_MODEL}\n")

    if DEEPSEEK_API_KEY:
        run_real_test()
    else:
        mock_self_check()
        print("\n【Mock 模式】待填入真实 Key 后重跑真实测试。")


if __name__ == "__main__":
    main()
