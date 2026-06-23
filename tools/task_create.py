"""创建任务工具。"""

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from .base import BaseTool, ToolResult


# 任务的内存存储（后续可改为持久化存储）
_task_store: Dict[str, Dict[str, Any]] = {}


class TaskCreateTool(BaseTool):
    name = "task_create"
    description = "创建一个新的结构化任务项用于跟踪工作进度"

    async def execute(self, **kwargs) -> ToolResult:
        subject = kwargs.get("subject", "")
        description = kwargs.get("description", "")
        active_form = kwargs.get("activeForm", None)
        metadata = kwargs.get("metadata", None)

        if not subject:
            return ToolResult(success=False, error="缺少必要参数: subject")

        task_id = uuid4().hex[:8]
        task = {
            "id": task_id,
            "subject": subject,
            "description": description or "",
            "activeForm": active_form,
            "status": "pending",
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        _task_store[task_id] = task

        return ToolResult(
            success=True,
            data={
                "task_id": task_id,
                "subject": subject,
                "status": "pending",
                "total_tasks": len(_task_store),
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
                        "subject": {
                            "type": "string",
                            "description": "任务简短标题（祈使句形式，如 'Fix authentication bug'）",
                        },
                        "description": {
                            "type": "string",
                            "description": "任务的详细描述",
                        },
                        "activeForm": {
                            "type": "string",
                            "description": "进行时态的任务描述（如 'Fixing authentication bug'），用于进度展示",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "附加元数据",
                        },
                    },
                    "required": ["subject"],
                },
            },
        }
