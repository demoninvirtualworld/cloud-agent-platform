"""创建定时任务工具 — Cron 表达式 + asyncio 调度器。

支持标准 5 字段 cron 表达式（分 时 日 月 周）。
调度器基于 asyncio 事件循环，在进程中运行。
"""

import asyncio
import calendar
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from .base import BaseTool, ToolResult


# ---------------------------------------------------------------------------
# Cron 表达式解析器
# ---------------------------------------------------------------------------

class CronParser:
    """
    解析标准 5 字段 cron 表达式并计算下次执行时间。

    支持:
    - 通配符: *
    - 范围: 1-5
    - 步长: */5
    - 列表: 1,3,5
    - 组合: 1-5,10-15/2
    """

    FIELD_NAMES = ["minute", "hour", "day", "month", "weekday"]
    FIELD_RANGES = {
        "minute": (0, 59),
        "hour": (0, 23),
        "day": (1, 31),
        "month": (1, 12),
        "weekday": (0, 6),  # 0=Sunday
    }

    def __init__(self, cron_expr: str):
        self.cron_expr = cron_expr.strip()
        self.fields = self.cron_expr.split()

        if len(self.fields) != 5:
            raise ValueError(
                f"Cron 表达式需要 5 个字段，当前有 {len(self.fields)} 个: '{self.cron_expr}'"
            )

        self.parsed: List[Set[int]] = []
        for i, field in enumerate(self.fields):
            name = self.FIELD_NAMES[i]
            lo, hi = self.FIELD_RANGES[name]
            self.parsed.append(self._parse_field(field, lo, hi, name))

    def _parse_field(
        self, field: str, lo: int, hi: int, name: str
    ) -> Set[int]:
        """解析单个字段为允许值集合。"""
        result: Set[int] = set()

        for part in field.split(","):
            part = part.strip()
            step = 1

            if "/" in part:
                part, step_str = part.split("/", 1)
                step = int(step_str)

            if part == "*":
                start, end = lo, hi
            elif "-" in part:
                start_str, end_str = part.split("-", 1)
                start, end = int(start_str), int(end_str)
            else:
                start = end = int(part)

            for v in range(start, end + 1, step):
                if lo <= v <= hi:
                    result.add(v)

        if not result:
            raise ValueError(
                f"无效的 cron 字段 '{field}' ({name}): 无匹配值"
            )

        return result

    def next_after(self, dt: datetime) -> Optional[datetime]:
        """计算给定时间之后的下一次触发时间。"""
        current = dt + timedelta(minutes=1)
        current = current.replace(second=0, microsecond=0)

        # 搜索上限：365 天
        for _ in range(525600):
            if (
                current.minute in self.parsed[0]
                and current.hour in self.parsed[1]
                and current.day in self.parsed[2]
                and current.month in self.parsed[3]
                and current.weekday() in self.parsed[4]
            ):
                return current
            current += timedelta(minutes=1)

        return None  # 一年内无匹配


# ---------------------------------------------------------------------------
# Cron 调度器
# ---------------------------------------------------------------------------

class CronScheduler:
    """
    基于 asyncio 的 cron 调度器。

    每个 job 以独立 asyncio.Task 运行，sleep 到下次执行时间。
    """

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._callback = None  # 执行回调: async def callback(job) -> None

    def set_callback(self, callback):
        """设置任务触发回调。"""
        self._callback = callback

    def add_job(
        self,
        job_id: str,
        cron_expr: str,
        prompt: str,
        recurring: bool = True,
    ) -> Dict[str, Any]:
        """添加一个定时任务并启动。"""
        try:
            parser = CronParser(cron_expr)
        except ValueError as e:
            raise ValueError(str(e)) from e

        job = {
            "id": job_id,
            "cron": cron_expr,
            "prompt": prompt,
            "parser": parser,
            "recurring": recurring,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "run_count": 0,
            "active": True,
        }
        self._jobs[job_id] = job

        # 启动 asyncio Task
        task = asyncio.create_task(self._run_job(job_id))
        self._tasks[job_id] = task

        return job

    def remove_job(self, job_id: str) -> bool:
        """停止并移除任务。"""
        if job_id not in self._jobs:
            return False
        self._jobs[job_id]["active"] = False
        task = self._tasks.pop(job_id, None)
        if task and not task.done():
            task.cancel()
        del self._jobs[job_id]
        return True

    def list_jobs(self) -> List[Dict[str, Any]]:
        """列出所有任务。"""
        return [
            {
                "id": j["id"],
                "cron": j["cron"],
                "prompt": j["prompt"][:100],
                "recurring": j["recurring"],
                "run_count": j["run_count"],
                "last_run": j["last_run"],
                "active": j["active"],
            }
            for j in self._jobs.values()
        ]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情。"""
        return self._jobs.get(job_id)

    async def stop_all(self) -> None:
        """停止所有任务。"""
        for job_id in list(self._jobs.keys()):
            self.remove_job(job_id)

    async def _run_job(self, job_id: str) -> None:
        """任务主循环。"""
        while True:
            job = self._jobs.get(job_id)
            if not job or not job["active"]:
                break

            # 计算下次执行时间
            now = datetime.now()
            next_time = job["parser"].next_after(now)

            if next_time is None:
                break  # 无更多触发时间

            # 等待到触发时间
            wait_seconds = (next_time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                try:
                    await asyncio.sleep(wait_seconds)
                except asyncio.CancelledError:
                    break

            # 触发回调
            if self._callback:
                try:
                    await self._callback(job)
                except Exception:
                    pass

            job["last_run"] = datetime.now().isoformat()
            job["run_count"] += 1

            # 一次性任务：执行后停止
            if not job["recurring"]:
                job["active"] = False
                break


# ---------------------------------------------------------------------------
# 全局调度器单例
# ---------------------------------------------------------------------------

_global_scheduler: Optional[CronScheduler] = None


def get_scheduler() -> CronScheduler:
    """获取全局调度器单例。"""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = CronScheduler()
    return _global_scheduler


def set_scheduler_callback(callback) -> None:
    """设置调度器的全局执行回调。"""
    scheduler = get_scheduler()
    scheduler.set_callback(callback)


# ---------------------------------------------------------------------------
# CreateCronTool
# ---------------------------------------------------------------------------

class CreateCronTool(BaseTool):
    name = "create_cron"
    description = "创建定时或周期性执行的计划任务"

    async def execute(self, **kwargs) -> ToolResult:
        cron = kwargs.get("cron", "")
        prompt = kwargs.get("prompt", "")
        recurring = kwargs.get("recurring", True)
        durable = kwargs.get("durable", False)

        # ── 参数校验 ──
        if not cron:
            return ToolResult(success=False, error="缺少必要参数: cron")
        if not prompt:
            return ToolResult(success=False, error="缺少必要参数: prompt")

        cron_parts = cron.strip().split()
        if len(cron_parts) != 5:
            return ToolResult(
                success=False,
                error=(
                    f"Cron 表达式格式错误: '{cron}'。"
                    "需要 5 个字段: 分 时 日 月 周\n"
                    "示例: '*/5 * * * *' (每5分钟), '0 9 * * 1-5' (工作日9点)"
                ),
            )

        # ── 验证表达式有效性 ──
        try:
            CronParser(cron)
        except ValueError as e:
            return ToolResult(success=False, error=str(e))

        # ── 创建并调度任务 ──
        job_id = uuid4().hex[:12]

        try:
            scheduler = get_scheduler()
            job = scheduler.add_job(
                job_id=job_id,
                cron_expr=cron,
                prompt=prompt,
                recurring=recurring,
            )
        except ValueError as e:
            return ToolResult(success=False, error=str(e))

        # ── 计算首次触发时间 ──
        parser = CronParser(cron)
        now = datetime.now()
        next_run = parser.next_after(now)
        next_run_str = next_run.isoformat() if next_run else "无（一年内无匹配）"

        return ToolResult(
            success=True,
            data={
                "job_id": job_id,
                "cron": cron,
                "prompt": prompt,
                "recurring": recurring,
                "durable": durable,
                "next_run": next_run_str,
                "status": "scheduled",
            },
        )

    @staticmethod
    def list_jobs() -> List[Dict[str, Any]]:
        """列出所有已创建的定时任务。"""
        return get_scheduler().list_jobs()

    @staticmethod
    def delete_job(job_id: str) -> bool:
        """删除指定定时任务。"""
        return get_scheduler().remove_job(job_id)

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
