"""启动子代理工具。"""

from typing import Any, Dict

from .base import BaseTool, ToolResult


class StartAgentTool(BaseTool):
    name = "start_agent"
    description = "启动一个新的子代理来执行独立任务"

    async def execute(self, **kwargs) -> ToolResult:
        description = kwargs.get("description", "")
        prompt = kwargs.get("prompt", "")
        subagent_type = kwargs.get("subagent_type", "general-purpose")
        model = kwargs.get("model", None)
        run_in_background = kwargs.get("run_in_background", False)

        if not prompt and not description:
            return ToolResult(
                success=False,
                error="缺少必要参数: prompt 或 description 至少需要一个",
            )

        # 注意：子代理启动需要 Agent Runtime 支持。
        # 当前为骨架实现 —— 上层 Agent Runtime 将处理子代理的完整生命周期。
        task_description = description or prompt

        return ToolResult(
            success=True,
            data={
                "task": task_description,
                "subagent_type": subagent_type,
                "model": model,
                "background": run_in_background,
                "status": "delegated",
                "note": (
                    "子代理任务已接收。完整的子代理编排将在 Agent Runtime 中实现。"
                    "当前可使用 Agent 工具类直接在进程中创建子代理。"
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
                        "description": {
                            "type": "string",
                            "description": "子代理任务的简短描述（3-5 词）",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "子代理要执行的任务说明",
                        },
                        "subagent_type": {
                            "type": "string",
                            "description": "子代理类型，如 'general-purpose', 'Explore', 'Plan' 等",
                            "default": "general-purpose",
                        },
                        "model": {
                            "type": "string",
                            "enum": ["sonnet", "opus", "haiku"],
                            "description": "子代理使用的模型",
                        },
                        "run_in_background": {
                            "type": "boolean",
                            "description": "是否在后台运行子代理",
                            "default": False,
                        },
                    },
                    "required": ["description", "prompt"],
                },
            },
        }
