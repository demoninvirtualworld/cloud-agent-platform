"""执行工作流工具。"""

from typing import Any, Dict

from .base import BaseTool, ToolResult


class RunWorkflowTool(BaseTool):
    name = "run_workflow"
    description = "执行多代理工作流脚本，编排多个子代理协同完成任务"

    async def execute(self, **kwargs) -> ToolResult:
        script = kwargs.get("script", None)
        name = kwargs.get("name", None)
        args = kwargs.get("args", None)
        script_path = kwargs.get("scriptPath", None)
        resume_from_run_id = kwargs.get("resumeFromRunId", None)

        if not any([script, name, script_path]):
            return ToolResult(
                success=False,
                error="缺少必要参数: script、name 或 scriptPath 至少需要一个",
            )

        source = (
            f"script '{name}'" if name
            else f"inline script ({len(script)} chars)" if script
            else f"file '{script_path}'"
        )

        # 注意：工作流执行需要 Workflow Engine 支持。
        # 当前为骨架实现 —— 上层 Workflow Engine 将负责工作流的解析和执行。
        return ToolResult(
            success=True,
            data={
                "source": source,
                "args": args,
                "resume_from": resume_from_run_id,
                "status": "scheduled",
                "note": (
                    "工作流已接收。Workflow Engine 将在后续版本中实现，"
                    "届时将支持并行/流水线代理编排、进度追踪和断点续传。"
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
                        "script": {
                            "type": "string",
                            "description": "自包含的工作流脚本（JavaScript），以 'export const meta = {...}' 开头",
                        },
                        "name": {
                            "type": "string",
                            "description": "预定义工作流名称（从 .claude/workflows/ 加载）",
                        },
                        "scriptPath": {
                            "type": "string",
                            "description": "工作流脚本文件路径",
                        },
                        "args": {
                            "description": "传递给工作流脚本的输入值（通过全局变量 args 访问）",
                        },
                        "resumeFromRunId": {
                            "type": "string",
                            "description": "之前运行的 ID，用于断点续传",
                        },
                    },
                    "required": [],
                },
            },
        }
