"""网络搜索工具 — 支持 DuckDuckGo、SerpAPI、Brave 等多后端。"""

import re
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from .base import BaseTool, ToolResult


# ---------------------------------------------------------------------------
# 搜索结果类型
# ---------------------------------------------------------------------------

class SearchResult:
    """单条搜索结果。"""
    def __init__(self, title: str, url: str, snippet: str):
        self.title = title
        self.url = url
        self.snippet = snippet

    def to_dict(self) -> Dict[str, str]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


# ---------------------------------------------------------------------------
# 搜索后端接口
# ---------------------------------------------------------------------------

class SearchBackend:
    """搜索后端的抽象接口。"""

    async def search(
        self, query: str, timeout: int = 15
    ) -> List[SearchResult]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# DuckDuckGo 后端（免费，无需 API Key）
# ---------------------------------------------------------------------------

class DuckDuckGoBackend(SearchBackend):
    """
    使用 DuckDuckGo Instant Answer API + HTML 回退进行搜索。

    API 文档: https://duckduckgo.com/api
    无需 API Key，但有限速。HTML 回退用于补充 API 未覆盖的结果。
    """

    API_URL = "https://api.duckduckgo.com/"

    async def search(
        self, query: str, timeout: int = 15
    ) -> List[SearchResult]:
        results: List[SearchResult] = []

        async with httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "CloudAgentPlatform/0.1"},
        ) as client:
            # 第一步：Instant Answer API
            api_results = await self._search_api(client, query)
            results.extend(api_results)

            # 第二步：HTML 搜索结果页（补充更多结果）
            if len(results) < 5:
                html_results = await self._search_html(client, query)
                # 去重合并
                existing_urls = {r.url for r in results}
                for r in html_results:
                    if r.url not in existing_urls:
                        results.append(r)
                        existing_urls.add(r.url)

        # 最多返回 15 条
        return results[:15]

    async def _search_api(
        self, client: httpx.AsyncClient, query: str
    ) -> List[SearchResult]:
        """调用 DuckDuckGo Instant Answer API。"""
        try:
            resp = await client.get(
                self.API_URL,
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results: List[SearchResult] = []

            # Abstract（摘要）
            if data.get("AbstractText") and data.get("AbstractURL"):
                results.append(SearchResult(
                    title=data.get("Heading", query),
                    url=data["AbstractURL"],
                    snippet=data["AbstractText"],
                ))

            # RelatedTopics（相关主题）
            for topic in data.get("RelatedTopics", []):
                if isinstance(topic, dict):
                    text = topic.get("Text", "")
                    url = topic.get("FirstURL", "")
                    if text and url:
                        # 分离标题和描述
                        parts = text.split(" - ", 1)
                        title = parts[0].strip() if parts else text[:80]
                        snippet = parts[1].strip() if len(parts) > 1 else ""
                        results.append(SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                        ))

            # Results（外部结果）
            for item in data.get("Results", []):
                if isinstance(item, dict):
                    url = item.get("FirstURL", "")
                    text = item.get("Text", "")
                    if url:
                        results.append(SearchResult(
                            title=text[:100] if text else url,
                            url=url,
                            snippet=text,
                        ))

            return results

        except Exception:
            return []

    async def _search_html(
        self, client: httpx.AsyncClient, query: str
    ) -> List[SearchResult]:
        """解析 DuckDuckGo HTML 搜索结果页（不依赖 JavaScript）。"""
        try:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            resp.raise_for_status()
            html = resp.text

            results: List[SearchResult] = []

            # 匹配结果块
            result_blocks = re.findall(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                html,
                re.DOTALL,
            )

            for href, title_html, snippet_html in result_blocks:
                title = unescape(re.sub(r"<[^>]+>", "", title_html)).strip()
                snippet = unescape(re.sub(r"<[^>]+>", "", snippet_html)).strip()
                if href.startswith("//"):
                    href = "https:" + href

                if title:
                    results.append(SearchResult(
                        title=title,
                        url=href,
                        snippet=snippet,
                    ))

            return results

        except Exception:
            return []


# ---------------------------------------------------------------------------
# SerpAPI 后端（需要 API Key）
# ---------------------------------------------------------------------------

class SerpAPIBackend(SearchBackend):
    """SerpAPI 搜索后端。需要 config.json 中配置 search.api_key。"""

    API_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(
        self, query: str, timeout: int = 15
    ) -> List[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    self.API_URL,
                    params={
                        "q": query,
                        "api_key": self.api_key,
                        "engine": "google",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                results: List[SearchResult] = []
                for item in data.get("organic_results", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                    ))
                return results[:15]

        except Exception:
            return []


# ---------------------------------------------------------------------------
# Brave Search 后端（需要 API Key）
# ---------------------------------------------------------------------------

class BraveSearchBackend(SearchBackend):
    """Brave Search API 后端。需要 config.json 中配置 search.api_key。"""

    API_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(
        self, query: str, timeout: int = 15
    ) -> List[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    self.API_URL,
                    params={"q": query, "count": 15},
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": self.api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                results: List[SearchResult] = []
                for item in data.get("web", {}).get("results", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("description", ""),
                    ))
                return results[:15]

        except Exception:
            return []


# ---------------------------------------------------------------------------
# 后端工厂
# ---------------------------------------------------------------------------

def _resolve_backend() -> SearchBackend:
    """
    根据配置解析搜索后端。

    优先级:
    1. config.json 中 search.backend 指定
    2. 否则默认 DuckDuckGo（免费，无需 Key）
    """
    try:
        from config import load_config
        config = load_config()
        search_config = config.get("search", {})
        backend_name = search_config.get("backend", "duckduckgo").lower()
        api_key = search_config.get("api_key", "")

        if backend_name == "serpapi" and api_key:
            return SerpAPIBackend(api_key)
        elif backend_name == "brave" and api_key:
            return BraveSearchBackend(api_key)
        elif backend_name == "duckduckgo":
            return DuckDuckGoBackend()
        else:
            # 配置了后端但缺少 API Key → 降级到 DuckDuckGo
            return DuckDuckGoBackend()
    except Exception:
        return DuckDuckGoBackend()


# ---------------------------------------------------------------------------
# WebSearchTool
# ---------------------------------------------------------------------------

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "在互联网上搜索信息并返回结果摘要"

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        allowed_domains = kwargs.get("allowed_domains", None)
        blocked_domains = kwargs.get("blocked_domains", None)

        if not query:
            return ToolResult(success=False, error="缺少必要参数: query")

        if len(query) < 2:
            return ToolResult(
                success=False,
                error="查询字符串至少需要 2 个字符",
            )

        try:
            backend = _resolve_backend()
            results = await backend.search(query)

            # 域名过滤
            if results and (allowed_domains or blocked_domains):
                filtered: List[SearchResult] = []
                for r in results:
                    from urllib.parse import urlparse
                    try:
                        domain = urlparse(r.url).netloc.lower()
                        # 去掉 www. 前缀便于匹配
                        if domain.startswith("www."):
                            domain = domain[4:]
                    except Exception:
                        domain = ""

                    # 白名单过滤
                    if allowed_domains:
                        allowed = [d.lower().lstrip("www.") for d in allowed_domains]
                        if not any(domain.endswith(d) for d in allowed):
                            continue

                    # 黑名单过滤
                    if blocked_domains:
                        blocked = [d.lower().lstrip("www.") for d in blocked_domains]
                        if any(domain.endswith(d) for d in blocked):
                            continue

                    filtered.append(r)
                results = filtered

            if not results:
                return ToolResult(
                    success=True,
                    data={
                        "query": query,
                        "results": [],
                        "note": f"未找到与 '{query}' 相关的结果。",
                    },
                )

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": [r.to_dict() for r in results],
                    "result_count": len(results),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"搜索请求失败: {str(e)}",
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
