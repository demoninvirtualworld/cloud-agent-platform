"""工具注册表 — 管理和查找所有可用工具。"""

from typing import Any, Dict, List, Optional

from .base import BaseTool


class ToolRegistry:
    """全局工具注册表，用于注册、查找和获取工具。"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具实例。"""
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Expected a BaseTool instance, got {type(tool).__name__}")
        if not tool.name:
            raise ValueError("Tool must have a non-empty name")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """注销指定名称的工具。"""
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        """根据名称获取工具实例。"""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """返回所有已注册工具的元信息列表。"""
        return [
            {"name": t.name, "description": t.description}
            for t in self._tools.values()
        ]

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """返回所有工具的 JSON Schema 列表。"""
        return [t.get_schema() for t in self._tools.values()]

    def clear(self) -> None:
        """清空注册表。"""
        self._tools.clear()
