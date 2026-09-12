# -*- coding: utf-8 -*-
"""server.py —— FastAPI 入口：静态页 + 健康检查 + 决策透视 + 对话。"""
import os
import agent

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
except Exception as e:  # pragma: no cover
    print("缺少依赖，请先安装：pip install -r requirements.txt")
    raise e

app = FastAPI(title="澄初 AI 导购 v2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/health")
def health():
    return agent.sanity_ping()


@app.get("/api/trace")
def api_trace(text: str = ""):
    return agent.trace(text)


@app.post("/api/chat")
def api_chat(payload: dict):
    try:
        msgs = payload.get("messages", [])[-12:]  # 窗口，防上下文无限膨胀
        reply = agent.chat(msgs)
        return {"reply": reply}
    except Exception as e:
        return {"reply": "抱歉，刚才没听清，请再发一次～", "error": str(e)}
