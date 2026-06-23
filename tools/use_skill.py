"""调用技能工具。"""

from typing import Any, Dict

from .base import BaseTool, ToolResult


class UseSkillTool(BaseTool):
    name = "use_skill"
    description = "调用指定的技能（Slash Command）来执行专门的操作"

    async def execute(self, **kwargs) -> ToolResult:
        skill = kwargs.get("skill", "")
        args = kwargs.get("args", None)

        if not skill:
            return ToolResult(success=False, error="缺少必要参数: skill")

        # 注意：技能调用需要 Skill Registry 支持。
        # 当前为骨架实现 —— 上层 Skill Registry 将负责技能查找和执行。
        return ToolResult(
            success=True,
            data={
                "skill": skill,
                "args": args,
                "status": "invoked",
                "note": (
                    f"技能 '{skill}' 已接收。"
                    "技能注册表（Skill Registry）将在后续版本中实现，"
                    "届时将支持动态加载和调用技能模块。"
                ),
            },
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
                        "skill": {
                            "type": "string",
                            "description": "要调用的技能名称（不含前导斜杠），如 'code-review', 'verify'",
                        },
                        "args": {
                            "type": "string",
                            "description": "传递给技能的可选参数",
                        },
                    },
                    "required": ["skill"],
                },
            },
        }
