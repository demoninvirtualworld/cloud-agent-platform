"""Glob 文件模式匹配搜索工具。"""

from pathlib import Path
from typing import Any, Dict, List

from .base import BaseTool, ToolResult


class GlobSearchTool(BaseTool):
    name = "glob_search"
    description = "使用 glob 模式匹配查找文件，支持递归搜索"

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")

        if not pattern:
            return ToolResult(success=False, error="缺少必要参数: pattern")

        try:
            base = Path(search_path).resolve()
            if not base.exists():
                return ToolResult(
                    success=False,
                    error=f"搜索路径不存在: {search_path}",
                )

            # 使用 ** 模式递归搜索
            results: List[str] = []
            # 如果 pattern 包含 **，使用全局递归
            if "**" in pattern:
                matches = sorted(base.glob(pattern))
            else:
                # 否则在当前目录及子目录搜索
                matches = sorted(base.rglob(pattern))

            # 去重并转为相对路径字符串
            seen: set = set()
            for m in matches:
                if m.is_file() or m.is_dir():
                    rel = str(m.relative_to(base))
                    if rel not in seen:
                        results.append(rel)
                        seen.add(rel)

            return ToolResult(
                success=True,
                data={
                    "pattern": pattern,
                    "search_path": str(base),
                    "match_count": len(results),
                    "matches": results[:500],  # 最多返回 500 条
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"glob 搜索失败: {str(e)}",
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
                        "pattern": {
                            "type": "string",
                            "description": (
                                "glob 匹配模式，如 '**/*.py'、'src/**/*.ts'。"
                                "支持 ** 递归匹配"
                            ),
                        },
                        "path": {
                            "type": "string",
                            "description": "搜索根目录，默认为当前工作目录",
                            "default": ".",
                        },
                    },
                    "required": ["pattern"],
                },
            },
        }
