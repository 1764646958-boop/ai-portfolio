# -*- coding: utf-8 -*-
"""
WorkBuddy 原型 · 本地 LLM 后端（真实大模型接入）
===============================================
目的：让 P3 原型走「真实大模型」做需求理解 + 语境适配打分，而不是仅用关键词近似。

安全约定：API Key 只存在于【本服务端】的环境变量或 .env 文件里，绝不下发到前端 HTML，
          避免 key 出现在共享文件/浏览器中。

依赖：仅标准库（http.server + urllib.request），无需 pip。
兼容：OpenAI Chat Completions 兼容协议（OpenAI / DeepSeek / Qwen(DashScope) / Moonshot / GLM 等多数中文大模型均为该协议）。

配置（三选一）：
  1) 环境变量：  set LLM_API_KEY=sk-xxx   LLM_BASE_URL=https://api.xxx/v1   LLM_MODEL=gpt-4o-mini
  2) .env 文件： 复制 .env.example 为 .env 填入
  3) 直接改下方 DEFAULTS

运行：python server.py  ->  默认 http://127.0.0.1:8001
      前端 index.html 在「真实 LLM」模式下会向本服务 /llm 请求。
"""
import os, json, re, gzip, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# ---------- 读取 .env ----------
def load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")   # 兼容 OpenAI 协议
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "30"))

# 资产库能力维度（与前端 DIMS 一致），供 LLM 将需求映射到维度
DIMS = {
    "text": "文本生成", "img": "图像/视觉", "data": "数据分析", "code": "代码",
    "trans": "翻译", "video": "视频/音频", "food": "美食/烹饪", "medical": "医疗/健康",
    "meeting": "会议/办公", "finance": "金融/投资", "drink": "酒/饮品", "legal": "法律/合规",
}

# 资产候选（名称 + 一句话能力），供 LLM 打分语境适配度
ASSET_LIST = [
    {"id": "mb",   "name": "MeetingSummarizer",   "cn": "会议纪要大师",   "desc": "把会议/评审讨论整理成简洁要点"},
    {"id": "cr",   "name": "CodeRefactor",        "cn": "代码重构助手",   "desc": "重构代码、改写函数、解释程序"},
    {"id": "dt",   "name": "DocTranslator",       "cn": "多语言文档翻译", "desc": "中英互译技术/商务文档"},
    {"id": "fan",  "name": "DataAnalyst",         "cn": "金融数据洞察",   "desc": "财报/金融数据分析与可视化"},
    {"id": "film", "name": "VintageFilmRestorer", "cn": "老胶片修复文案", "desc": "老胶片/纪录片修复效果描述与叙事文案"},
    {"id": "sake", "name": "SakePairingAdvisor",  "cn": "清酒配餐顾问",   "desc": "根据菜品/食材推荐清酒与佐餐搭配"},
    {"id": "med",  "name": "CTReportParser",      "cn": "医学CT报告解析", "desc": "解析医学影像/CT报告、提炼要点"},
    {"id": "soy",  "name": "SoyMilkRecipeBot",    "cn": "自制豆浆食谱",   "desc": "自制豆浆/五谷浆的配方与做法"},
    {"id": "hqt",  "name": "HighQualityTranslator", "cn": "精译大师",     "desc": "高质量中英互译，交付严谨、术语一致"},
]


def llm_chat(messages, want_json=True):
    """调用 OpenAI 兼容接口，返回文本（尽量解析 JSON）。"""
    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    # 请求会带上 Accept-Encoding，多数服务端会回 gzip，需自行解压
    payload = {"model": LLM_MODEL, "messages": messages, "temperature": 0.2}
    if want_json:
        payload["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + LLM_API_KEY,
                 "Accept-Encoding": "identity"},  # 请求不要压缩，简化解压
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        # 把错误体带出来，便于定位（如模型名不存在）
        body = e.read().decode("utf-8", "replace")[:600]
        raise RuntimeError(f"LLM HTTP {e.code}: {body}")
    # 兜底解压（若服务端仍返回 gzip）
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    data = json.loads(raw.decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def sys_prompt():
    dims_txt = json.dumps(DIMS, ensure_ascii=False)
    assets_txt = json.dumps([{ "id": a["id"], "name": a["name"], "cn": a["cn"], "desc": a["desc"]}
                             for a in ASSET_LIST], ensure_ascii=False)
    return (
        "你是 WorkBuddy 平台的需求理解 + 资产匹配引擎。请严格只输出 JSON 对象。\n"
        "可用能力维度：" + dims_txt + "\n"
        "候选资产：" + assets_txt + "\n\n"
        "对用户需求，输出：\n"
        '{ "intent": { "dims": ["按 DIMS 的 key 选出最相关的1-3个"], "entities": ["抽出的关键词/实体"],'
        ' "cluster": "需求所属簇(办公/开发/金融/医疗/生活/影视/法律/教育)", "isLongtail": true/假 },'
        ' "fits": { "资产id": 0-1的语境适配度, ... } }\n\n'
        "fits 是对【每个候选资产】与【当前需求】契合度的打分，0 表示几乎无关、1 表示完美契合。"
        "请只依据【候选资产的能力描述】与【当前需求】的语义匹配度打分；无视任何资产的人气、调用量或知名度，"
        "契合度越高给分越高、越不相关越低——不要因名气大小或是否属于头部而人为抬高或压低分数。"
    )


def handle_llm(text):
    msgs = [{"role": "system", "content": sys_prompt()},
            {"role": "user", "content": "用户需求：" + text}]
    raw = llm_chat(msgs)
    # 容错解析：去掉可能的 markdown 代码围栏
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.M).strip()
    obj = json.loads(raw)
    # 归一化 fits
    fits = {}
    for a in ASSET_LIST:
        v = obj.get("fits", {}).get(a["id"])
        try:
            fits[a["id"]] = max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            fits[a["id"]] = 0.0
    return {"intent": obj.get("intent", {}), "fits": fits, "raw": raw}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, open("index.html", "rb").read(), "text/html")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if urlparse(self.path).path != "/llm":
            self._send(404, json.dumps({"error": "not found"})); return
        if not LLM_API_KEY:
            self._send(500, json.dumps({"error": "未配置 LLM_API_KEY，请填写 .env 或环境变量"})); return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            text = body.get("text", "")
            if not text.strip():
                self._send(400, json.dumps({"error": "empty input"})); return
            out = handle_llm(text)
            self._send(200, json.dumps(out, ensure_ascii=False))
        except urllib.error.HTTPError as e:
            self._send(502, json.dumps({"error": "LLM 返回错误", "detail": e.read().decode("utf-8", "ignore")[:500]}))
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))

    def log_message(self, fmt, *args):
        pass  # 安静


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"WorkBuddy 原型 LLM 后端运行于 http://127.0.0.1:{port}")
    print(f"  模型: {LLM_MODEL} | Base: {LLM_BASE_URL}")
    print(f"  API Key: {'已配置' if LLM_API_KEY else '未配置(请填 .env / 环境变量)'}")
    print("  打开 http://127.0.0.1:8001/index.html 并在原型上选择「真实 LLM」模式 →")
    srv.serve_forever()
