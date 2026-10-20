# -*- coding: utf-8 -*-
"""DeepSeek API 客户端封装（OpenAI 兼容格式）。

《防线》项目 LLM 引擎统一走 DeepSeek API：
- base_url: https://api.deepseek.com
- model: deepseek-chat（可通过 .env 的 DEEPSEEK_MODEL 覆盖）
- API Key 从 W1/.env 读取（DEEPSEEK_API_KEY），禁止硬编码。

用法示例::

    from deepseek_client import DeepSeekClient

    client = DeepSeekClient()
    resp = client.chat([{"role": "user", "content": "你好"}])
    print(resp.choices[0].message.content)
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 定位 W1 根目录（本文件位于 W1/llm/ 下），显式加载 .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


class DeepSeekClient:
    """DeepSeek 客户端（OpenAI 兼容）。Key 为空时不初始化底层 client。"""

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = (api_key or DEEPSEEK_API_KEY).strip()
        self.base_url = base_url or DEEPSEEK_BASE_URL
        self.model = model or DEEPSEEK_MODEL
        self._client = None
        if self.api_key:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def is_ready(self):
        """是否已配置真实 Key（True 表示可发起真实网络请求）。"""
        return self._client is not None

    def chat(self, messages, json_mode=False, temperature=0.7, timeout=30):
        """发起一次对话补全。

        参数:
            messages: OpenAI 风格消息列表，形如 [{"role", "content"}, ...]
            json_mode: True 时附加 response_format={"type": "json_object"}
            temperature: 采样温度
            timeout: 请求超时秒数（默认 30s，防 LLM 慢响应卡住游戏线程）

        返回:
            完整的 OpenAI ChatCompletion 响应对象。
        """
        if not self.is_ready:
            raise RuntimeError(
                "DEEPSEEK_API_KEY 为空，客户端未初始化。请先在 W2/.env 填入 Key。"
            )
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return self._client.chat.completions.create(**kwargs)

    def retry_chat(self, messages, json_mode=False, max_retries=2,
                   temperature=0.7, timeout=30):
        """带指数退避重试的对话调用。

        参数:
            messages: OpenAI 风格消息列表
            json_mode: 是否要求 JSON 结构化输出
            max_retries: 失败后的额外重试次数（不含首次）
            temperature: 采样温度
            timeout: 单次请求超时秒数

        返回:
            str: 模型回复的文本内容（choices[0].message.content）。

        失败语义：重试耗尽后抛 RuntimeError（由 engines.run_engine 捕获并降级）。
        """
        import time

        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                resp = self.chat(messages, json_mode=json_mode,
                                 temperature=temperature, timeout=timeout)
                return resp.choices[0].message.content
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    time.sleep(0.5 * (2 ** attempt))  # 指数退避
        raise RuntimeError(f"DeepSeek 调用失败（重试 {max_retries} 次后）：{last_exc}")
