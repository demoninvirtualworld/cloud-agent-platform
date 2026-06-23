"""更新任务工具 — 状态管理 + 依赖追踪。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseTool, ToolResult
from .task_create import _task_store


# 合法的状态转换
_VALID_TRANSITIONS = {
    "pending": {"in_progress", "deleted"},
    "in_progress": {"completed", "pending", "deleted"},
    "completed": {"pending", "in_progress", "deleted"},
    "deleted": set(),  # 删除后不可恢复（软删除保留历史）
}

_VALID_STATUSES = {"pending", "in_progress", "completed", "deleted"}


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
                error=f"任务不存在: {task_id}。使用 task_create 创建新任务。",
            )

        old_status = task.get("status", "pending")

        # ── 状态更新 ──────────────────────────────────────────
        if status:
            if status not in _VALID_STATUSES:
                return ToolResult(
                    success=False,
                    error=(
                        f"无效的状态: '{status}'。"
                        f"有效值: {', '.join(sorted(_VALID_STATUSES))}"
                    ),
                )
            # 检查合法状态转换
            allowed = _VALID_TRANSITIONS.get(old_status, set())
            if status not in allowed and status != old_status:
                return ToolResult(
                    success=False,
                    error=(
                        f"不允许从 '{old_status}' 转换到 '{status}'。"
                        f"允许的转换: {', '.join(sorted(allowed)) if allowed else '无'}"
                    ),
                )
            task["status"] = status

        # ── 标题 / 描述更新 ───────────────────────────────────
        if subject:
            task["subject"] = subject

        if description:
            task["description"] = description

        if active_form:
            task["activeForm"] = active_form

        # ── 依赖关系更新 ──────────────────────────────────────
        if add_blocks:
            task.setdefault("blocks", [])
            for bid in add_blocks:
                if bid not in task["blocks"]:
                    task["blocks"].append(bid)
                # 双向关联：被阻塞的任务反向记录
                if bid in _task_store:
                    _task_store[bid].setdefault("blockedBy", [])
                    if task_id not in _task_store[bid]["blockedBy"]:
                        _task_store[bid]["blockedBy"].append(task_id)

        if add_blocked_by:
            task.setdefault("blockedBy", [])
            for bid in add_blocked_by:
                if bid not in task["blockedBy"]:
                    task["blockedBy"].append(bid)
                # 双向关联
                if bid in _task_store:
                    _task_store[bid].setdefault("blocks", [])
                    if task_id not in _task_store[bid]["blocks"]:
                        _task_store[bid]["blocks"].append(task_id)

        # ── 元数据合并 ────────────────────────────────────────
        if metadata:
            task.setdefault("metadata", {})
            task["metadata"].update(metadata)

        task["updated_at"] = datetime.now().isoformat()

        # 构建变更摘要
        changes: List[str] = []
        if status and status != old_status:
            changes.append(f"状态: {old_status} → {status}")
        if subject:
            changes.append("标题已更新")
        if description:
            changes.append("描述已更新")
        if add_blocks:
            changes.append(f"+{len(add_blocks)} 个阻塞任务")
        if add_blocked_by:
            changes.append(f"+{len(add_blocked_by)} 个被阻塞关系")

        return ToolResult(
            success=True,
            data={
                "task_id": task_id,
                "subject": task["subject"],
                "status": task["status"],
                "changes": changes,
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
                            "enum": list(_VALID_STATUSES),
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
