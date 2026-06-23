"""写入文件内容工具。"""

from pathlib import Path
from typing import Any, Dict

from .base import BaseTool, ToolResult


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "将内容写入指定文件（覆盖已有文件或创建新文件）"

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")

        if not file_path:
            return ToolResult(success=False, error="缺少必要参数: file_path")
        if content is None:
            return ToolResult(success=False, error="缺少必要参数: content")

        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                success=True,
                data={
                    "file_path": str(path.absolute()),
                    "bytes_written": len(content.encode("utf-8")),
                    "chars_written": len(content),
                },
            )
        except PermissionError:
            return ToolResult(
                success=False,
                error=f"没有写入权限: {file_path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"写入文件失败: {str(e)}",
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
                            "description": "要写入的文件绝对路径",
                        },
                        "content": {
                            "type": "string",
                            "description": "要写入的文件内容",
                        },
                    },
                    "required": ["file_path", "content"],
                },
            },
        }
