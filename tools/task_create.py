"""创建任务工具 — 内存存储 + 辅助查询方法。"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .base import BaseTool, ToolResult


# 任务的内存存储（跨工具共享，进程级生命周期）
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
            "blocks": [],
            "blockedBy": [],
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

    # ------------------------------------------------------------------
    # 辅助查询（供其他工具或测试使用）
    # ------------------------------------------------------------------

    @staticmethod
    def list_tasks(
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出所有任务，可按状态过滤。

        Args:
            status_filter: 可选的状态过滤器（pending / in_progress / completed / deleted）

        Returns:
            任务摘要列表（按创建时间排序）
        """
        tasks = list(_task_store.values())
        if status_filter:
            tasks = [t for t in tasks if t.get("status") == status_filter]
        tasks.sort(key=lambda t: t.get("created_at", ""))
        return [
            {
                "id": t["id"],
                "subject": t["subject"],
                "status": t["status"],
                "description": t.get("description", "")[:100],
            }
            for t in tasks
        ]

    @staticmethod
    def get_task(task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务详情。"""
        return _task_store.get(task_id)

    @staticmethod
    def delete_task(task_id: str) -> bool:
        """删除指定任务（同时清理其他任务中的依赖引用）。"""
        if task_id not in _task_store:
            return False

        # 清理依赖引用
        for t in _task_store.values():
            if task_id in t.get("blocks", []):
                t["blocks"].remove(task_id)
            if task_id in t.get("blockedBy", []):
                t["blockedBy"].remove(task_id)

        del _task_store[task_id]
        return True

    @staticmethod
    def clear_all() -> None:
        """清空所有任务（主要用于测试清理）。"""
        _task_store.clear()

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
