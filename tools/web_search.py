"""网络搜索工具。"""

from typing import Any, Dict

from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "在互联网上搜索信息并返回结果摘要"

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        allowed_domains = kwargs.get("allowed_domains", None)
        blocked_domains = kwargs.get("blocked_domains", None)

        if not query:
            return ToolResult(success=False, error="缺少必要参数: query")

        # 注意：WebSearch 需要搜索引擎 API 后端支持。
        # 当前为骨架实现，返回提示信息。
        # 后续可对接 Bing Search API、SerpAPI 或自建搜索引擎。
        return ToolResult(
            success=True,
            data={
                "query": query,
                "allowed_domains": allowed_domains,
                "blocked_domains": blocked_domains,
                "results": [],
                "note": (
                    "WebSearch 工具当前未配置搜索引擎后端。"
                    "请设置 SEARCH_API_KEY 和 SEARCH_API_URL 环境变量以启用搜索功能。"
                    "支持的搜索引擎: Bing Search API, SerpAPI, Brave Search API"
                ),
            },
            metadata={"backend_available": False},
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询字符串",
                            "minLength": 2,
                        },
                        "allowed_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "可选的允许域名列表（白名单过滤）",
                        },
                        "blocked_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "可选的阻止域名列表（黑名单过滤）",
                        },
                    },
                    "required": ["query"],
                },
            },
        }
