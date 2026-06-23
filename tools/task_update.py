"""更新任务工具。"""

from datetime import datetime
from typing import Any, Dict

from .base import BaseTool, ToolResult
from .task_create import _task_store


class TaskUpdateTool(BaseTool):
    name = "task_update"
    description = "更新已有任务的状态、标题或其他信息"

    async def execute(self, **kwargs) -> ToolResult:
        task_id = kwargs.get("taskId", "")
        status = kwargs.get("status", None)
        subject = kwargs.get("subject", None)
        description = kwargs.get("description", None)
        active_form = kwargs.get("activeForm", None)
        add_blocks = kwargs.get("addBlocks", None)
        add_blocked_by = kwargs.get("addBlockedBy", None)
        metadata = kwargs.get("metadata", None)

        if not task_id:
            return ToolResult(success=False, error="缺少必要参数: taskId")

        task = _task_store.get(task_id)
        if not task:
            return ToolResult(
                success=False,
                error=f"任务不存在: {task_id}",
            )

        # 更新字段
        if status:
            valid_statuses = {"pending", "in_progress", "completed", "deleted"}
            if status not in valid_statuses:
                return ToolResult(
                    success=False,
                    error=f"无效的状态: {status}。有效值: {', '.join(valid_statuses)}",
                )
            task["status"] = status

        if subject:
            task["subject"] = subject

        if description:
            task["description"] = description

        if active_form:
            task["activeForm"] = active_form

        if add_blocks:
            task.setdefault("blocks", []).extend(add_blocks)

        if add_blocked_by:
            task.setdefault("blockedBy", []).extend(add_blocked_by)

        if metadata:
            task["metadata"].update(metadata)

        task["updated_at"] = datetime.now().isoformat()

        return ToolResult(
            success=True,
            data={
                "task_id": task_id,
                "subject": task["subject"],
                "status": task["status"],
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
                        "taskId": {
                            "type": "string",
                            "description": "要更新的任务 ID",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "deleted"],
                            "description": "任务新状态",
                        },
                        "subject": {
                            "type": "string",
                            "description": "新的任务标题",
                        },
                        "description": {
                            "type": "string",
                            "description": "新的任务描述",
                        },
                        "activeForm": {
                            "type": "string",
                            "description": "新的进行时态描述",
                        },
                        "addBlocks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "被此任务阻塞的任务 ID 列表",
                        },
                        "addBlockedBy": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "阻塞此任务的任务 ID 列表",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "要合并的元数据键值对",
                        },
                    },
                    "required": ["taskId"],
                },
            },
        }
