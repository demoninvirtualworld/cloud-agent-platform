"""内容搜索工具（基于正则表达式）。"""

import re
from pathlib import Path
from typing import Any, Dict, List

from .base import BaseTool, ToolResult


class GrepSearchTool(BaseTool):
    name = "grep_search"
    description = "在文件内容中使用正则表达式搜索匹配的文本行"

    async def execute(self, **kwargs) -> ToolResult:
        search_pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")
        glob_filter = kwargs.get("glob", None)
        output_mode = kwargs.get("output_mode", "files_with_matches")
        case_insensitive = kwargs.get("case_insensitive", False)
        head_limit = kwargs.get("head_limit", 250)
        context_lines = kwargs.get("context", 0)

        if not search_pattern:
            return ToolResult(success=False, error="缺少必要参数: pattern")

        try:
            flags = re.IGNORECASE if case_insensitive else 0
            if kwargs.get("multiline", False):
                flags |= re.DOTALL
            regex = re.compile(search_pattern, flags)
        except re.error as e:
            return ToolResult(
                success=False,
                error=f"正则表达式语法错误: {str(e)}",
            )

        try:
            base = Path(search_path).resolve()
            if not base.exists():
                return ToolResult(
                    success=False,
                    error=f"搜索路径不存在: {search_path}",
                )

            # 确定搜索的文件列表
            if glob_filter:
                files = list(base.rglob(glob_filter))
            else:
                # 默认搜索常见文本文件
                text_extensions = {
                    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml",
                    ".yml", ".toml", ".cfg", ".ini", ".md", ".txt", ".rst",
                    ".html", ".css", ".scss", ".sql", ".sh", ".bash", ".ps1",
                    ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
                    ".rb", ".php", ".xml", ".svg", ".csv", ".env",
                }
                files = [
                    f for f in base.rglob("*")
                    if f.is_file() and f.suffix in text_extensions
                ]

            results: List[Dict[str, Any]] = []
            total_matches = 0
            files_with_matches: List[str] = []

            for file_path in sorted(files):
                if head_limit:
                    if output_mode == "files_with_matches" and len(files_with_matches) >= head_limit:
                        break
                    if output_mode == "content" and len(results) >= head_limit:
                        break

                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except (PermissionError, OSError):
                    continue

                file_matches: List[Dict[str, Any]] = []
                for line_num, line in enumerate(lines, start=1):
                    match = regex.search(line)
                    if match:
                        file_matches.append({
                            "line": line_num,
                            "text": line.rstrip(),
                            "match": match.group(),
                        })
                        total_matches += 1

                if file_matches:
                    rel_path = str(file_path.relative_to(base))
                    files_with_matches.append(rel_path)

                    if output_mode == "content":
                        for m in file_matches:
                            if head_limit and len(results) >= head_limit:
                                break
                            result_entry: Dict[str, Any] = {
                                "file": rel_path,
                                "line": m["line"],
                                "text": m["text"],
                            }
                            if context_lines > 0:
                                start = max(0, m["line"] - context_lines - 1)
                                end = min(len(lines), m["line"] + context_lines)
                                result_entry["context"] = (
                                    "".join(lines[start:end]).rstrip()
                                )
                            results.append(result_entry)

            if output_mode == "count":
                return ToolResult(
                    success=True,
                    data={
                        "pattern": search_pattern,
                        "total_matches": total_matches,
                        "files_searched": len(files),
                        "files_with_matches": len(files_with_matches),
                    },
                )

            return ToolResult(
                success=True,
                data={
                    "pattern": search_pattern,
                    "search_path": str(base),
                    "files_searched": len(files),
                    "files_with_matches": files_with_matches,
                    "total_matches": total_matches,
                    "results": results if output_mode == "content" else None,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"文本搜索失败: {str(e)}",
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
                            "description": "正则表达式搜索模式",
                        },
                        "path": {
                            "type": "string",
                            "description": "搜索根目录，默认为当前工作目录",
                            "default": ".",
                        },
                        "glob": {
                            "type": "string",
                            "description": (
                                "文件过滤 glob 模式，如 '*.py'、'*.{ts,tsx}'。"
                                "不指定则搜索所有文本文件"
                            ),
                        },
                        "output_mode": {
                            "type": "string",
                            "enum": ["content", "files_with_matches", "count"],
                            "description": "输出模式: content(匹配行), files_with_matches(文件路径), count(计数)",
                            "default": "files_with_matches",
                        },
                        "case_insensitive": {
                            "type": "boolean",
                            "description": "是否忽略大小写",
                            "default": False,
                        },
                        "multiline": {
                            "type": "boolean",
                            "description": "是否启用多行模式（. 匹配换行符）",
                            "default": False,
                        },
                        "context": {
                            "type": "integer",
                            "description": "匹配行前后显示的行数",
                            "default": 0,
                        },
                        "head_limit": {
                            "type": "integer",
                            "description": "最大返回结果数",
                            "default": 250,
                        },
                    },
                    "required": ["pattern"],
                },
            },
        }
