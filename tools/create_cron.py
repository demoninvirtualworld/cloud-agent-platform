"""创建定时任务工具。"""

from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from .base import BaseTool, ToolResult


# 定时任务的内存存储（后续可改为持久化存储）
_cron_jobs: Dict[str, Dict[str, Any]] = {}


class CreateCronTool(BaseTool):
    name = "create_cron"
    description = "创建定时或周期性执行的计划任务"

    async def execute(self, **kwargs) -> ToolResult:
        cron = kwargs.get("cron", "")
        prompt = kwargs.get("prompt", "")
        recurring = kwargs.get("recurring", True)
        durable = kwargs.get("durable", False)

        if not cron:
            return ToolResult(success=False, error="缺少必要参数: cron")
        if not prompt:
            return ToolResult(success=False, error="缺少必要参数: prompt")

        # 基本 cron 格式校验（5 字段）
        cron_parts = cron.strip().split()
        if len(cron_parts) != 5:
            return ToolResult(
                success=False,
                error=(
                    f"Cron 表达式格式错误: '{cron}'。"
                    "需要 5 个字段: 分 时 日 月 周"
                ),
            )

        job_id = uuid4().hex[:12]
        job = {
            "id": job_id,
            "cron": cron,
            "prompt": prompt,
            "recurring": recurring,
            "durable": durable,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "run_count": 0,
        }

        _cron_jobs[job_id] = job

        return ToolResult(
            success=True,
            data={
                "job_id": job_id,
                "cron": cron,
                "recurring": recurring,
                "durable": durable,
                "note": (
                    "定时任务已创建。Cron 调度器将在后续版本中实现，"
                    "届时将支持自动按时触发任务。"
                ),
            },
        )

    @staticmethod
    def list_jobs() -> List[Dict[str, Any]]:
        """列出所有已创建的定时任务。"""
        return list(_cron_jobs.values())

    @staticmethod
    def delete_job(job_id: str) -> bool:
        """删除指定定时任务。"""
        if job_id in _cron_jobs:
            del _cron_jobs[job_id]
            return True
        return False

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cron": {
                            "type": "string",
                            "description": (
                                "标准 5 字段 cron 表达式（本地时间）: "
                                "'分 时 日 月 周'。示例: '*/5 * * * *' (每5分钟), "
                                "'0 9 * * 1-5' (工作日9点)"
                            ),
                        },
                        "prompt": {
                            "type": "string",
                            "description": "每次触发时执行的提示词",
                        },
                        "recurring": {
                            "type": "boolean",
                            "description": "是否为重复任务（false 则为一次性任务）",
                            "default": True,
                        },
                        "durable": {
                            "type": "boolean",
                            "description": "是否持久化到磁盘（跨会话存活）",
                            "default": False,
                        },
                    },
                    "required": ["cron", "prompt"],
                },
            },
        }
