# -*- coding: utf-8 -*-
"""
《防线》 · llm_server/llm_server.py
LLM HTTP 服务端（标准库 http.server，零第三方 Web 框架）

给 Godot 侧 llm_gateway.gd 的 HTTP 服务（base http://localhost:8000，POST JSON，前缀 /llm/）。

启动::
    python llm_server.py                      # 端口 8000
    python llm_server.py --port 9000          # 自定义端口
    python llm_server.py --mock               # 强制 Mock（即使 Key 不为空也不发真实请求）

端点清单（POST /llm/{endpoint} → 响应均为 JSON，字段与 llm_gateway.gd 期望一致）：
  /llm/analyze_memory         → {drift_direction, magnitude, confidence}
  /llm/generate_dialogue      → {dialogue_text, warmth, manipulation, helpfulness}
  /llm/analyze_fake_memory    → {fake_variants[3], source}
  /llm/battle_dialogue        → {strategy, key_lines[], pressure_level}
  /llm/generate_name          → {generated_name, generation_reason}
  /llm/validate_player_line   → {is_valid, matched_line, matched_line_id, confidence,
                                 ai_reaction_hint, reason}   ← W5 T1（场景 5.4 选项 B）

错误处理：请求解析失败/未知端点/引擎失败 → 统一返回 HTTP 200 + {"error": "..."}（Godot 侧按 200 读 JSON，
再检查 error 字段，避免 HTTPRequest 把非 200 当失败导致二次降级）。

Key 策略：从 .env 读 DEEPSEEK_API_KEY（查找顺序：llm_server/.env → 仓库根 .env → 环境变量）；
为空时自动使用 MockClient（返回同形 mock 响应，不崩溃）。.env 模板见仓库根 .env.example。
"""

import argparse
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SERVER_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVER_DIR.parent

# .env 查找顺序：llm_server/.env → 仓库根 .env
for _env_path in (SERVER_DIR / ".env", REPO_ROOT / ".env"):
    if _env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(_env_path)
        break

from deepseek_client import DeepSeekClient
from engines import MockClient, degrade_validate_player_line, run_engine

logger = logging.getLogger("llm_server")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)

# 端点 → 引擎名（与 llm_gateway.gd 接口一一对应；前五个为 W3.1/W4.1 五端点，
# validate_player_line 为 W5 T1 新增第 6 端点）
ENDPOINT_TO_ENGINE = {
    "analyze_memory": "memory_analysis",
    "generate_dialogue": "dialogue",
    "analyze_fake_memory": "fake_memory",
    "battle_dialogue": "battle_dialogue",
    "generate_name": "name_generation",
    "validate_player_line": "validate_player_line",
}

# 各端点的输入字段白名单（payload → build kwargs 映射；
# value 为 str 时：payload 字段名 → kwargs 参数名（不同名时映射）
ENDPOINT_FIELDS = {
    "analyze_memory": [("template_text", "template_text"), ("player_emotion", "player_emotion"), ("anchor_id", "anchor_id")],
    "generate_dialogue": [("context", "context"), ("npc_character", "npc_character"), ("player_history_summary", "player_history_summary")],
    "analyze_fake_memory": [("template_text", "template_text"), ("trust_drift", "trust_bias"),
                            ("anchor_id", "anchor_id"), ("twistable_elements", "twistable_elements")],
    "battle_dialogue": [("player_profile", "player_profile"), ("trust_drift", "trust_drift"), ("avoided_anchors", "avoided_anchors")],
    "generate_name": [("player_texts_summary", "player_texts_summary")],
    "validate_player_line": [("player_line", "player_line"), ("context", "context")],
}


def load_anchors_twistable() -> dict:
    """加载仓库 config/anchors.json 的 twistable_elements 兜底表（可选）。

    llm_gateway.gd 未传 twistable_elements 时，server 按 anchor_id 自动补全，
    保证 V3 prompt 的硬约束始终生效。加载失败只警告，不阻断服务。
    """
    path = REPO_ROOT / "config" / "anchors.json"
    result = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for aid, entry in data.items():
            if isinstance(entry, dict) and "llm_params" in entry:
                tw = entry["llm_params"].get("twistable_elements")
                if isinstance(tw, list):
                    result[aid] = tw
        logger.info("anchors.json twistable_elements 表已加载：%d 条锚点", len(result))
    except Exception as e:
        logger.warning("anchors.json 加载失败（%s）；twistable_elements 需调用方传入", e)
    return result


TWISTABLE_CACHE = {}


def handle_endpoint(client, endpoint: str, payload: dict) -> dict:
    """处理单个端点请求，返回响应 dict（含 error 时也以 dict 形式返回）。"""
    if endpoint not in ENDPOINT_TO_ENGINE:
        return {"error": f"unknown endpoint: {endpoint}，可用：{sorted(ENDPOINT_TO_ENGINE)}"}

    engine_name = ENDPOINT_TO_ENGINE[endpoint]
    kwargs = {}
    for payload_field, kwarg_field in ENDPOINT_FIELDS[endpoint]:
        if payload_field in payload:
            kwargs[kwarg_field] = payload[payload_field]

    # fake_memory：调用方未传 twistable_elements 时按 anchor_id 从 anchors.json 兜底
    if endpoint == "analyze_fake_memory" and "twistable_elements" not in kwargs:
        anchor_id = str(kwargs.get("anchor_id", ""))
        if anchor_id in TWISTABLE_CACHE:
            kwargs["twistable_elements"] = TWISTABLE_CACHE[anchor_id]
        else:
            kwargs.setdefault("twistable_elements", None)

    logger.info("[%-20s] payload keys=%s → kwargs=%s",
                endpoint, list(payload.keys()), list(kwargs.keys()))
    result = run_engine(client, engine_name, **kwargs)
    if result is None:
        # validate_player_line 的契约要求「降级也同形」（不返回 error）：
        # Godot 侧据 is_valid=false / hint="ignore" 直接走"没想起这句话"的演出分支
        if endpoint == "validate_player_line":
            logger.warning("validate_player_line 引擎全失败 → 返回降级同形响应")
            return degrade_validate_player_line()
        return {"error": f"engine '{engine_name}' 全部失败（LLM 失败且无规则兜底）"}
    return result


class LlmRequestHandler(BaseHTTPRequestHandler):
    """POST /llm/{endpoint} 请求处理器。"""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 静默默认访问日志（用 logging 代替）
        logger.info("[http] %s %s", self.address_string(), fmt % args)

    def do_POST(self):
        # 解析路径：/llm/analyze_memory
        path = self.path.split("?", 1)[0]
        if not path.startswith("/llm/"):
            self._respond(200, {"error": f"path must start with /llm/，收到：{path!r}"})
            return
        endpoint = path[len("/llm/"):]

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            payload = json.loads(body.decode("utf-8")) if body else {}
            if not isinstance(payload, dict):
                self._respond(200, {"error": "body 必须是 JSON 对象"})
                return
            response = handle_endpoint(self.server.llm_client, endpoint, payload)
        except json.JSONDecodeError:
            response = {"error": "body 不是合法 JSON"}
        except Exception as e:  # 防御：任何内部异常都返回 200 + error
            logger.error("[%s] 内部异常：%s", endpoint, e, exc_info=True)
            response = {"error": f"internal error: {e}"}

        self._respond(200, response)

    def _respond(self, status: int, data: dict) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")  # Godot 侧无 CORS 限制，保留以便调试
        self.end_headers()
        self.wfile.write(raw)


def make_server(host: str, port: int, client) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), LlmRequestHandler)
    server.daemon_threads = True
    server.llm_client = client
    return server


def main():
    parser = argparse.ArgumentParser(description="《防线》LLM HTTP 服务端（W3.1）")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument("--mock", action="store_true", help="强制 Mock（不发起真实请求）")
    parser.add_argument("--log", default="INFO", help="日志级别（默认 INFO）")
    args = parser.parse_args()

    logging.getLogger("engines").setLevel(args.log.upper())

    # Key 检测：--mock 强制 Mock；Key 为空自动 Mock
    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    use_mock = args.mock or not api_key
    client = MockClient() if use_mock else DeepSeekClient()

    global TWISTABLE_CACHE
    TWISTABLE_CACHE = load_anchors_twistable()

    server = make_server(args.host, args.port, client)

    print("=" * 72)
    print("《防线》LLM HTTP 服务端 · llm_server v0.3（W5：+ validate_player_line 第 6 端点）")
    print(f"  监听：http://{args.host}:{args.port}")
    print(f"  模式：{'MOCK（Key 空/--mock，返回同形 mock 响应）' if use_mock else '真实 DeepSeek'}")
    print("  端点清单（POST /llm/{endpoint}）：")
    for ep in ENDPOINT_TO_ENGINE:
        print(f"    POST /llm/{ep}")
    print("  关闭：Ctrl+C")
    print("=" * 72)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[llm_server] 收到 Ctrl+C，关闭服务。")
        server.server_close()


if __name__ == "__main__":
    main()
