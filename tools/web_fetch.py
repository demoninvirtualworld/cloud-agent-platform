"""网页内容获取工具。"""

from typing import Any, Dict
from urllib.parse import urlparse

import httpx

from .base import BaseTool, ToolResult


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "获取 URL 内容并返回解析后的文本（转为 Markdown 格式）"

    # 请求超时（秒）
    TIMEOUT = 30
    # 最大响应大小（字节）
    MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB

    async def execute(self, **kwargs) -> ToolResult:
        url = kwargs.get("url", "")
        prompt = kwargs.get("prompt", "")

        if not url:
            return ToolResult(success=False, error="缺少必要参数: url")

        # 基本 URL 验证
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return ToolResult(
                    success=False,
                    error=f"无效的 URL: {url}",
                )
            if parsed.scheme not in ("http", "https"):
                return ToolResult(
                    success=False,
                    error=f"不支持的协议: {parsed.scheme}",
                )
        except Exception:
            return ToolResult(
                success=False,
                error=f"URL 解析失败: {url}",
            )

        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT,
                follow_redirects=True,
                headers={
                    "User-Agent": "CloudAgentPlatform/0.1",
                },
            ) as client:
                # 如果提供了 prompt，先获取页面再让调用方处理
                response = await client.get(url)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")

                # 只处理文本内容
                if "text/html" in content_type or "text/plain" in content_type:
                    text = response.text[: self.MAX_RESPONSE_SIZE]
                elif "application/json" in content_type:
                    text = response.text[: self.MAX_RESPONSE_SIZE]
                else:
                    return ToolResult(
                        success=False,
                        error=f"不支持的内容类型: {content_type}。仅支持 text/html, text/plain, application/json",
                    )

                return ToolResult(
                    success=True,
                    data={
                        "url": str(response.url),
                        "status_code": response.status_code,
                        "content_type": content_type,
                        "content_length": len(text),
                        "content": text,
                        "prompt": prompt or None,
                    },
                    metadata={
                        "truncated": len(response.text) > self.MAX_RESPONSE_SIZE,
                    },
                )
        except httpx.HTTPStatusError as e:
            return ToolResult(
                success=False,
                error=f"HTTP {e.response.status_code}: {url}",
            )
        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                error=f"请求超时 ({self.TIMEOUT}s): {url}",
            )
        except httpx.RequestError as e:
            return ToolResult(
                success=False,
                error=f"请求失败: {str(e)}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"获取 URL 内容失败: {str(e)}",
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
                        "url": {
                            "type": "string",
                            "description": "要获取内容的 URL（仅支持 HTTP/HTTPS）",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "可选的提示词，用于指导如何处理获取到的内容",
                        },
                    },
                    "required": ["url"],
                },
            },
        }
