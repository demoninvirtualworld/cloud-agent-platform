"""读取文件内容工具。"""

from pathlib import Path
from typing import Any, Dict

from .base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取指定文件的内容，支持分页和行范围"

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 2000)

        if not file_path:
            return ToolResult(success=False, error="缺少必要参数: file_path")

        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"文件不存在: {file_path}",
                )
            if not path.is_file():
                return ToolResult(
                    success=False,
                    error=f"路径不是文件: {file_path}",
                )

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            start = max(0, offset)
            end = min(total_lines, start + limit) if limit > 0 else total_lines
            selected = lines[start:end]

            # 构建带行号的输出
            output_lines = []
            for i, line in enumerate(selected, start=start + 1):
                output_lines.append(f"{i}\t{line.rstrip()}")

            return ToolResult(
                success=True,
                data={
                    "file_path": str(path.absolute()),
                    "total_lines": total_lines,
                    "start_line": start + 1 if selected else 0,
                    "end_line": start + len(selected),
                    "content": "\n".join(output_lines),
                },
            )
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error=f"文件不是文本格式，无法读取: {file_path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"读取文件失败: {str(e)}",
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
                        "file_path": {
                            "type": "string",
                            "description": "要读取的文件绝对路径",
                        },
                        "offset": {
                            "type": "integer",
                            "description": "起始行号（从 0 开始），默认为 0",
                            "default": 0,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "最大读取行数，默认 2000",
                            "default": 2000,
                        },
                    },
                    "required": ["file_path"],
                },
            },
        }
