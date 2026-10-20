"""LangChain Agent 可调用的工具（@tool 装饰的函数）。"""

from backend.tools.knowledge import make_search_knowledge_base

__all__ = ["make_search_knowledge_base"]
