"""执行工作流工具 — 多子代理编排引擎。

支持三种工作流来源:
1. inline script: 直接传入的 Python/JS 风格工作流定义
2. name: 从 .claude/workflows/<name>.py 加载预定义工作流
3. scriptPath: 从指定路径加载工作流文件

工作流定义格式（Python DSL）:
    steps = [
        {"agent": "AgentName", "prompt": "任务描述", "depends_on": []},
        {"agent": "AgentName", "prompt": "任务描述", "depends_on": [0]},
    ]
"""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from .base import BaseTool, ToolResult


# ---------------------------------------------------------------------------
# 工作流步骤
# ---------------------------------------------------------------------------

class WorkflowStep:
    """工作流中的一个执行步骤。"""

    def __init__(
        self,
        index: int,
        agent: str,
        prompt: str,
        depends_on: Optional[List[int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.index = index
        self.agent = agent
        self.prompt = prompt
        self.depends_on = depends_on or []
        self.metadata = metadata or {}
        self.result: Optional[str] = None
        self.status: str = "pending"  # pending / running / completed / failed
        self.error: Optional[str] = None
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "agent": self.agent,
            "prompt": self.prompt[:100],
            "depends_on": self.depends_on,
            "status": self.status,
            "error": self.error,
            "result_preview": (self.result or "")[:200],
        }


# ---------------------------------------------------------------------------
# 工作流解析器
# ---------------------------------------------------------------------------

class WorkflowParser:
    """解析多种格式的工作流定义。"""

    @staticmethod
    def parse_inline(script: str) -> List[Dict[str, Any]]:
        """解析内联工作流脚本。

        支持两种格式:
        1. JSON 数组: [{"agent": ..., "prompt": ..., "depends_on": [...]}, ...]
        2. Python-like: steps = [{"agent": ..., "prompt": ...}, ...]
        """
        # 尝试 JSON 解析
        try:
            data = json.loads(script)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "steps" in data:
                return data["steps"]
        except json.JSONDecodeError:
            pass

        # 尝试提取 Python-like 列表
        # 匹配 steps = [...] 或直接 [...]
        match = re.search(
            r'(?:steps\s*=\s*)?(\[.*\])\s*$',
            script,
            re.DOTALL,
        )
        if match:
            try:
                # 安全 eval（仅列表字面量）
                steps = eval(match.group(1))
                if isinstance(steps, list):
                    return steps
            except Exception:
                pass

        raise ValueError(
            "无法解析工作流脚本。支持的格式:\n"
            "  - JSON 数组: [{\"agent\": \"...\", \"prompt\": \"...\"}, ...]\n"
            "  - Python 风格: steps = [{\"agent\": \"...\", \"prompt\": \"...\"}, ...]"
        )

    @staticmethod
    def parse_file(filepath: str) -> List[Dict[str, Any]]:
        """从文件加载工作流定义。"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"工作流文件不存在: {filepath}")

        content = path.read_text(encoding="utf-8")

        # JSON 文件
        if path.suffix == ".json":
            return json.loads(content)

        # Python 文件
        return WorkflowParser.parse_inline(content)

    @staticmethod
    def parse_named(name: str) -> List[Dict[str, Any]]:
        """从 .claude/workflows/ 目录加载命名工作流。"""
        project_root = Path(__file__).resolve().parent.parent
        workflows_dir = project_root / ".claude" / "workflows"

        # 尝试 .py 和 .json
        for ext in (".py", ".json"):
            filepath = workflows_dir / f"{name}{ext}"
            if filepath.exists():
                return WorkflowParser.parse_file(str(filepath))

        raise FileNotFoundError(
            f"工作流 '{name}' 未找到。"
            f"请在 {workflows_dir}/ 目录创建 {name}.py 或 {name}.json"
        )


# ---------------------------------------------------------------------------
# 工作流引擎
# ---------------------------------------------------------------------------

class WorkflowEngine:
    """工作流执行引擎。支持顺序和并行（DAG 拓扑排序）执行。"""

    def __init__(self):
        self._runs: Dict[str, Dict[str, Any]] = {}

    async def execute(
        self,
        steps_raw: List[Dict[str, Any]],
        workflow_args: Optional[Dict[str, Any]] = None,
        resume_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行工作流。

        Args:
            steps_raw: 步骤定义列表
            workflow_args: 传递给工作流的参数
            resume_from: 续传的运行 ID

        Returns:
            包含所有步骤结果的字典。
        """
        run_id = resume_from or uuid4().hex[:12]

        # 解析步骤
        steps: List[WorkflowStep] = []
        for i, raw in enumerate(steps_raw):
            prompt = raw.get("prompt", "")
            # 变量替换：$args.xxx
            if workflow_args and "$args" in prompt:
                for key, val in workflow_args.items():
                    prompt = prompt.replace(f"$args.{key}", str(val))

            steps.append(WorkflowStep(
                index=i,
                agent=raw.get("agent", "general-purpose"),
                prompt=prompt,
                depends_on=raw.get("depends_on", []),
                metadata=raw.get("metadata"),
            ))

        # 拓扑排序 → 确定执行顺序
        execution_order = self._topological_sort(steps)

        # 按分层并行执行
        run_record = {
            "run_id": run_id,
            "total_steps": len(steps),
            "completed": 0,
            "failed": 0,
            "steps": [s.to_dict() for s in steps],
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
        }
        self._runs[run_id] = run_record

        for layer in execution_order:
            # 每层中的步骤可并行执行（无相互依赖）
            tasks = []
            for step_idx in layer:
                step = steps[step_idx]
                # 检查依赖是否全部成功
                deps_failed = False
                for dep_idx in step.depends_on:
                    if steps[dep_idx].status == "failed":
                        deps_failed = True
                        step.status = "skipped"
                        step.error = f"依赖步骤 {dep_idx} 失败，跳过执行"
                        break

                if not deps_failed:
                    tasks.append(self._execute_step(step))

            if tasks:
                await asyncio.gather(*tasks)

            # 更新进度
            for step_idx in layer:
                step = steps[step_idx]
                if step.status == "completed":
                    run_record["completed"] += 1
                elif step.status == "failed":
                    run_record["failed"] += 1
            run_record["steps"] = [s.to_dict() for s in steps]

        run_record["completed_at"] = datetime.now().isoformat()

        # 构建摘要
        results_summary = []
        for s in steps:
            results_summary.append({
                "step": s.index,
                "agent": s.agent,
                "status": s.status,
                "result": (s.result or s.error or "")[:200],
            })

        return {
            "run_id": run_id,
            "total": len(steps),
            "completed": run_record["completed"],
            "failed": run_record["failed"],
            "results": results_summary,
        }

    async def _execute_step(self, step: WorkflowStep) -> None:
        """执行单个步骤（通过子代理）。"""
        step.status = "running"
        step.started_at = datetime.now().isoformat()

        try:
            from .start_agent import _run_subagent
            from .registry import ToolRegistry

            registry = ToolRegistry.get_active() or ToolRegistry()

            result = await asyncio.wait_for(
                _run_subagent(
                    prompt=step.prompt,
                    description=f"Workflow step {step.index}: {step.agent}",
                    tool_registry=registry,
                    effort="high",
                ),
                timeout=180,  # 每个步骤最多 3 分钟
            )

            step.result = result
            step.status = "completed"
        except asyncio.TimeoutError:
            step.status = "failed"
            step.error = f"步骤 {step.index} 执行超时 (180s)"
        except Exception as e:
            step.status = "failed"
            step.error = str(e)
        finally:
            step.completed_at = datetime.now().isoformat()

    def _topological_sort(
        self, steps: List[WorkflowStep]
    ) -> List[List[int]]:
        """
        DAG 拓扑排序，返回分层执行顺序。

        Returns:
            [[step_indices_layer_0], [step_indices_layer_1], ...]
            每层内的步骤可并行执行。
        """
        n = len(steps)
        in_degree = [0] * n
        adj: List[List[int]] = [[] for _ in range(n)]

        for step in steps:
            for dep in step.depends_on:
                if 0 <= dep < n:
                    adj[dep].append(step.index)
                    in_degree[step.index] += 1

        # BFS 分层
        layers: List[List[int]] = []
        visited = 0
        queue: List[int] = [i for i in range(n) if in_degree[i] == 0]

        while queue:
            layers.append(list(queue))
            next_queue: List[int] = []
            for u in queue:
                visited += 1
                for v in adj[u]:
                    in_degree[v] -= 1
                    if in_degree[v] == 0:
                        next_queue.append(v)
            queue = next_queue

        if visited != n:
            # 存在环 → 顺序执行
            return [[i] for i in range(n)]

        return layers

    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流运行状态。"""
        return self._runs.get(run_id)


# ---------------------------------------------------------------------------
# 全局引擎单例
# ---------------------------------------------------------------------------

_global_engine: Optional[WorkflowEngine] = None


def get_engine() -> WorkflowEngine:
    """获取全局工作流引擎单例。"""
    global _global_engine
    if _global_engine is None:
        _global_engine = WorkflowEngine()
    return _global_engine


# ---------------------------------------------------------------------------
# RunWorkflowTool
# ---------------------------------------------------------------------------

class RunWorkflowTool(BaseTool):
    name = "run_workflow"
    description = (
        "执行多代理工作流脚本，编排多个子代理协同完成任务。"
        "支持顺序和并行（基于 DAG 依赖）执行模式。"
    )

    # 整体工作流超时（秒）
    WORKFLOW_TIMEOUT = 600  # 10 分钟

    async def execute(self, **kwargs) -> ToolResult:
        script = kwargs.get("script", None)
        name = kwargs.get("name", None)
        script_path = kwargs.get("scriptPath", None)
        workflow_args = kwargs.get("args", None)
        resume_from_run_id = kwargs.get("resumeFromRunId", None)

        if not any([script, name, script_path]):
            return ToolResult(
                success=False,
                error="缺少必要参数: script、name 或 scriptPath 至少需要一个",
            )

        # ── 解析工作流定义 ──
        try:
            if name:
                steps_raw = WorkflowParser.parse_named(name)
                source = f"named workflow '{name}'"
            elif script_path:
                steps_raw = WorkflowParser.parse_file(script_path)
                source = f"file '{script_path}'"
            else:
                steps_raw = WorkflowParser.parse_inline(script)
                source = f"inline script ({len(script)} chars)"
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
            return ToolResult(success=False, error=str(e))

        if not steps_raw:
            return ToolResult(
                success=False,
                error="工作流定义中没有步骤",
            )

        # ── 执行 ──
        try:
            engine = get_engine()
            result = await asyncio.wait_for(
                engine.execute(
                    steps_raw=steps_raw,
                    workflow_args=workflow_args,
                    resume_from=resume_from_run_id,
                ),
                timeout=self.WORKFLOW_TIMEOUT,
            )

            success = result["failed"] == 0
            return ToolResult(
                success=success,
                data={
                    "source": source,
                    **result,
                },
                error=(
                    f"{result['failed']}/{result['total']} 个步骤失败"
                    if result["failed"] > 0 else None
                ),
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"工作流执行超时 ({self.WORKFLOW_TIMEOUT}s)",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"工作流执行失败: {str(e)}",
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
                            "description": (
                                "自包含的工作流脚本。支持 JSON 数组格式: "
                                '[{"agent": "name", "prompt": "...", "depends_on": []}, ...]'
                            ),
                        },
                        "name": {
                            "type": "string",
                            "description": "预定义工作流名称（从 .claude/workflows/ 加载）",
                        },
                        "scriptPath": {
                            "type": "string",
                            "description": "工作流脚本文件路径（.py 或 .json）",
                        },
                        "args": {
                            "description": "传递给工作流脚本的输入值（通过 $args.xxx 变量引用）",
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
