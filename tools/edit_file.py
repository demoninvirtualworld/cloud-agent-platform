"""编辑文件内容工具（字符串替换）。"""

from pathlib import Path
from typing import Any, Dict

from .base import BaseTool, ToolResult


class EditFileTool(BaseTool):
    name = "edit_file"
    description = "对文件进行精确字符串替换编辑（单次或全部替换）"

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        old_string = kwargs.get("old_string", "")
        new_string = kwargs.get("new_string", "")
        replace_all = kwargs.get("replace_all", False)

        if not file_path:
            return ToolResult(success=False, error="缺少必要参数: file_path")
        if not old_string:
            return ToolResult(success=False, error="缺少必要参数: old_string")

        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"文件不存在: {file_path}",
                )

            with open(path, "r", encoding="utf-8") as f:
                original = f.read()

            if replace_all:
                count = original.count(old_string)
                if count == 0:
                    return ToolResult(
                        success=False,
                        error=f"未找到匹配的字符串（已搜索全部出现）",
                    )
                modified = original.replace(old_string, new_string)
            else:
                count = original.count(old_string)
                if count == 0:
                    return ToolResult(
                        success=False,
                        error=f"未找到匹配的字符串",
                    )
                if count > 1:
                    return ToolResult(
                        success=False,
                        error=(
                            f"找到 {count} 处匹配，但 replace_all 为 False。"
                            "请缩小 old_string 范围使其唯一，或设置 replace_all=True"
                        ),
                    )
                modified = original.replace(old_string, new_string, 1)

            if modified == original:
                return ToolResult(
                    success=False,
                    error="替换后内容未发生变化（new_string 与 old_string 相同）",
                )

            with open(path, "w", encoding="utf-8") as f:
                f.write(modified)

            return ToolResult(
                success=True,
                data={
                    "file_path": str(path.absolute()),
                    "replacements": 1 if not replace_all else count,
                    "old_length": len(old_string),
                    "new_length": len(new_string),
                },
            )
        except PermissionError:
            return ToolResult(
                success=False,
                error=f"没有文件编辑权限: {file_path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"编辑文件失败: {str(e)}",
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
                            "description": "要编辑的文件绝对路径",
                        },
                        "old_string": {
                            "type": "string",
                            "description": "要被替换的原始字符串（必须精确匹配，包括缩进）",
                        },
                        "new_string": {
                            "type": "string",
                            "description": "替换后的新字符串",
                        },
                        "replace_all": {
                            "type": "boolean",
                            "description": "是否替换所有匹配项（默认只替换唯一匹配）",
                            "default": False,
                        },
                    },
                    "required": ["file_path", "old_string", "new_string"],
                },
            },
        }
